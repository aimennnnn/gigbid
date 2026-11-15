"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { ErrorBox, RiskBadges, Status } from "@/components/Bits";
import { EvidenceHover } from "@/components/EvidenceHover";
import { RunTimeline } from "@/components/RunTimeline";
import { money, session, threadOf, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

type Critique = { approved: boolean; comments: string[] };
type Compliance = { passed: boolean; violations: string[]; removed: string[] };
type DryRun = { connects_cost?: number; connects_balance_after?: number; would_send?: { cover_letter?: string; amount?: number } };

export default function Studio() {
  const jobId = decodeURIComponent(String(useParams().id));
  const thread = threadOf(session()?.user ?? "", jobId);
  const path = `/proposals/${encodeURIComponent(thread)}`;
  const { data: d, error, loading, reload } = useApi<S["Studio"]>(path, 3000);
  const run = useApi<S["RunDetail"]>(`/runs/${encodeURIComponent(thread)}`, 3000);
  if (loading && !d) return <p className="muted">Loading the draft…</p>;
  if (!d) return <ErrorBox message={error ?? "There is no draft for this job yet. Analyse it from the inbox first."} />;
  const critique = d.critique as Critique | null;
  const compliance = d.compliance as Compliance | null;
  const dry = d.dry_run as DryRun | null;
  const price = d.price as { amount: number; connects_cost: number } | null;
  const risk = d.risk as { flags: string[] } | null;
  const claims = d.claims as { text: string; evidence_ids: string[]; status: string }[];
  const evidence = d.evidence as Record<string, { id: string; title?: string; text?: string }>;

  return (
    <>
      <p>
        <Link href={`/jobs/${jobId}`}>← {d.job_title}</Link>
      </p>
      <div className="head">
        <h1>Proposal studio</h1>
        <Status status={d.status} />
      </div>
      <ErrorBox message={d.errors.length ? d.errors.join(" · ") : null} />
      {!d.draft && <p className="muted">{d.running ? "The agents are still working on this job." : "No draft was written for this job."}</p>}
      {d.draft && (
        <div className="cols wide">
          <div className="stack">
            <section className="card">
              <h2>Draft</h2>
              <p className="muted small">Highlighted sentences are claims about your past work. Hover or tab to one to see the evidence behind it.</p>
              <EvidenceHover draft={d.draft} claims={claims} evidence={evidence} />
              {Object.keys(d.screening_answers ?? {}).length > 0 && (
                <>
                  <h3>Screening answers</h3>
                  <dl>
                    {Object.entries(d.screening_answers ?? {}).map(([q, a]) => (
                      <div key={q}>
                        <dt>{q}</dt>
                        <dd>{a}</dd>
                      </div>
                    ))}
                  </dl>
                </>
              )}
            </section>
            {d.pending && (
              <ApprovalPanel
                thread={thread}
                draft={d.draft}
                what={`Approving sends this proposal for ${money(price?.amount)} and spends ${dry?.connects_cost ?? price?.connects_cost ?? "?"} Connects.`}
                onDone={() => {
                  reload();
                  run.reload();
                }}
              />
            )}
            {d.status === "submitted" && (
              <p className="notice ok" data-testid="submitted-note">
                Submitted to the marketplace. Follow it on the <Link href="/pipeline">pipeline board</Link>.
              </p>
            )}
            {d.status === "rejected" && (
              <p className="notice" data-testid="rejected-note">
                You rejected this draft. Nothing was sent. {d.outcome}
              </p>
            )}
            {d.status === "needs_attention" && <p className="notice bad">This draft was blocked and was not sent. See the compliance notes.</p>}
          </div>
          <div className="stack">
            <section className="card">
              <h2>What will be sent</h2>
              <dl className="pairs">
                <div>
                  <dt>Price</dt>
                  <dd>{money(price?.amount)}</dd>
                </div>
                <div>
                  <dt>Connects cost</dt>
                  <dd>{dry?.connects_cost ?? price?.connects_cost ?? "-"}</dd>
                </div>
                <div>
                  <dt>Balance after</dt>
                  <dd>{dry?.connects_balance_after ?? "-"}</dd>
                </div>
              </dl>
              <p className="muted small">This is a dry run from the marketplace: it shows the cost without sending anything.</p>
              {risk && <RiskBadges flags={risk.flags} />}
            </section>
            <section className="card">
              <h2>Critic</h2>
              {!critique && <p className="muted">No review yet.</p>}
              {critique && <p>{critique.approved ? "Approved the draft." : "Asked for changes."}</p>}
              <ul>
                {critique?.comments.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </section>
            <section className="card">
              <h2>Compliance</h2>
              {compliance && <p>{compliance.passed ? "Passed the policy check." : "Blocked by the policy check."}</p>}
              <ul>
                {compliance?.violations.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
              {(d.removed_claims ?? []).length > 0 && (
                <>
                  <h3>Removed before you saw it</h3>
                  <p className="muted small">These sentences claimed something the evidence does not show.</p>
                  <ul>
                    {(d.removed_claims ?? []).map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
            {run.data && (
              <section className="card">
                <h2>Agent steps</h2>
                <RunTimeline thread={thread} initial={run.data.events} running={run.data.run.running} onSettled={reload} />
                <p>
                  <Link href={`/runs/${encodeURIComponent(thread)}`}>Open the full run and trace</Link>
                </p>
              </section>
            )}
          </div>
        </div>
      )}
    </>
  );
}
