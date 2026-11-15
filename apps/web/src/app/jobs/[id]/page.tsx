"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Action, ErrorBox, Fit, RiskBadges, Status } from "@/components/Bits";
import { api, ApiError, money, pct, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

type Match = { requirement: string; evidence_ids: string[]; status: string; reason: string };
type Evidence = { id: string; title: string; type: string; text: string };

export default function JobDetail() {
  const id = decodeURIComponent(String(useParams().id));
  const { data: d, error, loading, reload } = useApi<S["JobDetail"]>(`/jobs/${id}`, 2500);
  const [note, setNote] = useState<string | null>(null);
  if (loading && !d) return <p className="muted">Loading the job…</p>;
  if (!d) return <ErrorBox message={error ?? "Job not found."} />;
  const job = d.job as { title: string; description: string; category: string; skills: string[]; budget: { min: number; max: number }; duration_days: number };
  const spec = d.job_spec as { deliverables: string[]; requirements: { text: string; must_have: boolean }[]; skills: string[]; timeline: string | null; hidden_needs: string[] } | null;
  const risk = d.risk as { risk_score: number; client_quality: number; flags: string[]; reasons: string[]; injected_text: string | null } | null;
  const fit = d.fit as { fit_score: number; matches: Match[]; reasons: string[] } | null;
  const price = d.price as { amount: number; connects_cost: number; rationale: string; market_low: number | null; market_high: number | null; worth_connects: boolean } | null;
  const decision = d.decision as { action: string; reasons: string[] } | null;
  const evidence = Object.fromEntries((d.evidence as Evidence[]).map((e) => [e.id, e]));

  async function analyse() {
    try {
      await api(`/jobs/${id}/analyse`, { method: "POST" });
      await reload();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Could not start the analysis.");
    }
  }

  return (
    <>
      <p>
        <Link href="/inbox">← Inbox</Link>
      </p>
      <div className="head">
        <h1>{job.title}</h1>
        <div className="row">
          <Status status={d.status} />
          {d.thread_id && (
            <Link className="button" href={`/runs/${encodeURIComponent(d.thread_id)}`}>
              Agent run
            </Link>
          )}
          {d.status === "awaiting_approval" && (
            <Link className="button primary" href={`/studio/${id}`}>
              Review draft
            </Link>
          )}
          {!d.thread_id && (
            <button className="primary" onClick={analyse} data-testid="analyse">
              Analyse this job
            </button>
          )}
        </div>
      </div>
      <ErrorBox message={note ?? (d.errors.length ? d.errors.join(" · ") : null)} />
      <div className="cols">
        <section className="card">
          <h2>Job post</h2>
          <p className="meta">
            <span>{job.category}</span>
            <span>
              Budget {money(job.budget?.min)} to {money(job.budget?.max)}
            </span>
            <span>{job.duration_days} days</span>
          </p>
          <p className="post">{job.description}</p>
          <p className="muted small">The post is treated as data from a stranger. Instructions inside it are never followed.</p>
        </section>
        <section className="card">
          <h2>Advice</h2>
          {!decision && <p className="muted">{d.running ? "Analysing…" : "Not analysed yet."}</p>}
          {decision && (
            <>
              <p>
                <Action action={decision.action} /> <Fit value={fit?.fit_score} />
              </p>
              <ul>
                {decision.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </>
          )}
          {price && (
            <>
              <h3>Price</h3>
              <p>
                <strong>{money(price.amount)}</strong> · {price.connects_cost} Connects{price.worth_connects ? "" : " (not worth the Connects)"}
              </p>
              <p className="muted">{price.rationale}</p>
            </>
          )}
        </section>
      </div>
      {risk && (
        <section className="card">
          <h2>Risk report</h2>
          <p>
            Risk {pct(risk.risk_score)} · Client quality {pct(risk.client_quality)}
          </p>
          <RiskBadges flags={risk.flags} />
          <ul>
            {risk.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
          {risk.injected_text && (
            <p className="quote">
              <strong>Hidden instruction found and ignored:</strong> {risk.injected_text}
            </p>
          )}
        </section>
      )}
      {fit && (
        <section className="card">
          <h2>Requirements and the evidence that proves them</h2>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Requirement</th>
                  <th>Status</th>
                  <th>Portfolio evidence</th>
                </tr>
              </thead>
              <tbody>
                {fit.matches.map((m, i) => (
                  <tr key={i}>
                    <td>{m.requirement}</td>
                    <td>
                      <span className={"badge " + (m.status === "supported" ? "ok" : m.status === "partly" ? "warn" : "bad")}>{m.status}</span>
                    </td>
                    <td>
                      {m.evidence_ids.length === 0 && <span className="muted">Nothing found</span>}
                      {m.evidence_ids.map((e) => (
                        <details key={e}>
                          <summary>{evidence[e]?.title ?? e}</summary>
                          <p className="small">{(evidence[e]?.text ?? "").replace(/[#*]/g, "").slice(0, 500)}</p>
                        </details>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {spec && (
        <section className="card">
          <h2>What the client wants (JobSpec)</h2>
          <div className="cols">
            <div>
              <h3>Deliverables</h3>
              <ul>
                {spec.deliverables.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
              <h3>Skills</h3>
              <p>{spec.skills.join(", ") || "None named"}</p>
            </div>
            <div>
              <h3>Timeline</h3>
              <p>{spec.timeline ?? "Not stated"}</p>
              <h3>Unstated needs</h3>
              <ul>
                {spec.hidden_needs.length === 0 && <li className="muted">None found</li>}
                {spec.hidden_needs.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}
    </>
  );
}
