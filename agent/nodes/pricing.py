"""Pricing Strategist: a bid from market statistics, the client's budget and the user's
floor, and a yes/no on whether the Connects are worth spending. Plain arithmetic, no model:
a price should be explainable line by line."""
from agent.handoffs import PriceQuote
from agent.nodes.base import Deps, ids
from agent.settings import get_settings


def decide(state: dict) -> dict:
    """The 'bid or skip?' node: thresholds come from config, reasons are spelled out."""
    from agent.handoffs import BidDecision
    t, risk, fit = get_settings()["thresholds"], state.get("risk"), state.get("fit")
    if not risk or not fit or not state.get("job_spec"):
        return {"status": "dead_letter", "errors": ["decide: an analysis branch did not finish"]}
    supported = sum(m.status == "supported" for m in fit.matches)
    floor = state.get("profile", {}).get("min_budget", 0)
    budget_max = state["job"].get("budget", {}).get("max") or 0
    if risk.risk_score >= t["risk_block"]:
        action, why = "skip", [f"risk {risk.risk_score:.2f} is at or above {t['risk_block']}: {', '.join(risk.flags)}"]
    elif budget_max and budget_max < floor:
        action, why = "skip", [f"budget tops out at ${budget_max:.0f}, below your floor of ${floor}"]
    elif fit.fit_score >= t["fit_bid"] and supported >= t["min_evidence_items"]:
        action, why = "bid", [f"fit {fit.fit_score:.2f}, {supported} requirements backed by evidence, risk {risk.risk_score:.2f}"]
    elif fit.fit_score >= t["fit_watch"]:
        action, why = "watch", [f"fit {fit.fit_score:.2f} is between watch ({t['fit_watch']}) and bid ({t['fit_bid']})"]
    else:
        action, why = "skip", [f"fit {fit.fit_score:.2f} is below {t['fit_watch']}: not enough portfolio evidence"]
    if "prompt_injection" in risk.flags:
        why.append("the post contains instructions aimed at AI tools; they were ignored")
    status = {"bid": "drafting", "watch": "watching", "skip": "skipped"}[action]
    return {"decision": BidDecision(job_id=state["job_id"], action=action, reasons=why), "status": status, "steps_used": 1}


async def run(deps: Deps, state: dict, config: dict) -> dict:
    job, spec, who = state["job"], state["job_spec"], ids(state, config)
    rules = get_settings()["rules"]["connects"]
    stats = await deps.toolbox.call("pricing", "marketplace", "get_market_stats",
                                    {"category": job["category"], "skills": spec.skills[:10]}, **who)
    balance = (await deps.toolbox.call("pricing", "marketplace", "get_connects_balance", {}, **who))["balance"]
    floor = state.get("profile", {}).get("min_budget", 0)
    lo, hi = job["budget"]["min"], job["budget"]["max"]
    market = stats["p50"] or (lo + hi) / 2
    amount = max(floor, min(market, hi * 1.1))          # market middle, capped just above the client's budget
    cost = job.get("connects_cost", rules["cost_per_proposal_default"])
    worth = cost <= rules["max_cost_per_proposal"] and cost <= balance and amount >= floor
    why = (f"Similar closed jobs paid ${stats['p25']:.0f} to ${stats['p75']:.0f} (middle ${market:.0f}, {stats['n']} jobs). "
           f"The client's budget is ${lo:.0f} to ${hi:.0f} and your floor is ${floor}. Bid ${amount:.0f}. "
           f"Costs {cost} Connects of your {balance}: {'worth it' if worth else 'not worth it'}.")
    quote = PriceQuote(job_id=state["job_id"], amount=round(amount), price_type="fixed", connects_cost=cost,
                       worth_connects=worth, rationale=why, market_low=stats["p25"], market_high=stats["p75"])
    return {"price": quote} | ({} if worth else {"status": "skipped"})
