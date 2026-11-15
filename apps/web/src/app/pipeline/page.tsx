"use client";
import Link from "next/link";
import { Empty, ErrorBox } from "@/components/Bits";
import { money, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

const LABEL: Record<string, string> = { drafted: "Drafted", submitted: "Submitted", viewed: "Viewed", replied: "Replied", interview: "Interview", hired: "Hired", lost: "Lost" };

export default function Pipeline() {
  const { data, error, loading } = useApi<S["Pipeline"]>("/pipeline", 4000);
  return (
    <>
      <div className="head">
        <h1>Pipeline</h1>
        <span className="muted">Cards move when the marketplace reports an event.</span>
      </div>
      <ErrorBox message={error} />
      {loading && !data && <p className="muted">Loading…</p>}
      {data && data.cards.length === 0 && <Empty>No proposals yet. Analyse some jobs in the inbox; drafts appear here as soon as they are written.</Empty>}
      {data && data.cards.length > 0 && (
        <div className="board" data-testid="board">
          {data.stages.map((stage) => {
            const cards = data.cards.filter((c) => c.stage === stage);
            return (
              <section key={stage} className="column" aria-label={LABEL[stage]} data-stage={stage}>
                <h2>
                  {LABEL[stage]} <span className="count">{cards.length}</span>
                </h2>
                {cards.map((c) => (
                  <Link key={c.thread_id} href={`/studio/${c.job_id}`} className="kcard" data-testid="pipeline-card">
                    <strong>{c.title}</strong>
                    <span className="muted">
                      {c.category} · {money(c.amount)}
                    </span>
                  </Link>
                ))}
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
