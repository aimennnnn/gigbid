"""Job Analyst: job post -> structured JobSpec. No tools."""
from agent.handoffs import JobSpec
from agent.llm import ask
from agent.nodes.base import Deps


async def run(deps: Deps, state: dict, config: dict) -> dict:
    spec, tokens = await ask("analyst", {"job_post": state["job"]}, JobSpec, untrusted=("job_post",))
    spec.job_id = state["job_id"]                       # never trust an id that came back from the model
    return {"job_spec": spec, "tokens_used": tokens}
