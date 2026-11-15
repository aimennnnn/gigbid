"use client";
import Link from "next/link";
import { useState } from "react";
import { Action, Empty, ErrorBox, Fit, RiskBadges, Status } from "@/components/Bits";
import { api, ApiError, money, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

export default function Inbox() {
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const query = `/jobs?q=${encodeURIComponent(q)}${category ? `&category=${category}` : ""}`;
  const { data, error, loading, reload } = useApi<S["Inbox"]>(query, 2500);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setNote(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="head">
        <h1>Job inbox</h1>
        <div className="row">
          <button className="primary" disabled={busy} onClick={() => act(() => api("/jobs/analyse-new?limit=5", { method: "POST" }))} data-testid="analyse-new">
            Analyse 5 new jobs
          </button>
        </div>
      </div>
      <div className="filters">
        <label htmlFor="q" className="sr">
          Search
        </label>
        <input id="q" placeholder="Search jobs" value={q} onChange={(e) => setQ(e.target.value)} />
        <label htmlFor="cat" className="sr">
          Category
        </label>
        <select id="cat" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          <option value="ml">AI / ML</option>
          <option value="web">Web</option>
          <option value="data">Data</option>
        </select>
      </div>
      <ErrorBox message={note ?? error} />
      {loading && !data && <p className="muted">Loading jobs…</p>}
      {data && data.jobs.length === 0 && <Empty>No jobs match. Clear the search, or wait for new ones: GigSim posts a new job every two minutes.</Empty>}
      <ul className="jobs" data-testid="jobs">
        {data?.jobs.map((j) => (
          <li key={j.job_id} className={"job " + j.state} data-testid="job-row" data-action={j.action ?? ""} data-status={j.status ?? ""}>
            <div className="main">
              <Link href={`/jobs/${j.job_id}`} className="title">
                {j.title}
              </Link>
              <div className="meta">
                <span>{j.category}</span>
                <span>
                  Budget {money(j.budget_min)} to {money(j.budget_max)}
                </span>
                <span>{j.connects_cost ?? "-"} Connects</span>
                {j.state === "analysing" && <span className="status analysing">Analysing…</span>}
                {j.state === "skipped_by_you" && <span className="status skipped">Skipped by you</span>}
                {j.state === "analysed" && <Status status={j.status} />}
              </div>
              {j.state === "analysed" && (
                <>
                  <RiskBadges flags={j.risk_flags ?? []} />
                  {j.reasons?.[0] && <p className="why">{j.reasons[0]}</p>}
                </>
              )}
            </div>
            <div className="side">
              <div className="nums">
                <span>
                  <small>Fit</small>
                  <Fit value={j.fit} />
                </span>
                <span>
                  <small>Advice</small>
                  <Action action={j.action} />
                </span>
                <span>
                  <small>Price</small>
                  {money(j.price)}
                </span>
              </div>
              <div className="row end">
                {j.status === "awaiting_approval" && (
                  <Link className="button primary" href={`/studio/${j.job_id}`} data-testid="open-studio">
                    Review draft
                  </Link>
                )}
                {j.state === "new" && (
                  <button disabled={busy} onClick={() => act(() => api(`/jobs/${j.job_id}/analyse`, { method: "POST" }))}>
                    Analyse
                  </button>
                )}
                <Link className="button" href={`/jobs/${j.job_id}`}>
                  Open
                </Link>
                {j.state !== "skipped_by_you" && j.status !== "submitted" && (
                  <button className="link" disabled={busy} onClick={() => act(() => api(`/jobs/${j.job_id}/skip`, { json: { reason: "skipped by you" } }))}>
                    Skip
                  </button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}
