"use client";
import { Empty, ErrorBox } from "@/components/Bits";
import { pct, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

export default function Analytics() {
  const { data: a, error, loading } = useApi<S["Analytics"]>("/analytics", 6000);
  if (loading && !a) return <p className="muted">Loading…</p>;
  if (!a) return <ErrorBox message={error} />;
  return (
    <>
      <div className="head">
        <h1>Analytics</h1>
      </div>
      <div className="tiles">
        <div className="tile">
          <small>Proposals sent</small>
          <strong>{a.proposals}</strong>
        </div>
        <div className="tile">
          <small>Replies</small>
          <strong>{a.replies}</strong>
        </div>
        <div className="tile">
          <small>Hires</small>
          <strong>{a.hires}</strong>
        </div>
        <div className="tile">
          <small>Connects spent</small>
          <strong>{a.connects_spent}</strong>
        </div>
        <div className="tile">
          <small>Tokens per proposal</small>
          <strong>{a.tokens_per_proposal?.toLocaleString("en-US") ?? "-"}</strong>
        </div>
        <div className="tile">
          <small>Seconds to a draft</small>
          <strong>{a.seconds_per_proposal ?? "-"}</strong>
        </div>
      </div>
      <section className="card">
        <h2>Reply and hire rate by category</h2>
        {a.by_category.length === 0 && <Empty>Nothing sent yet, so there are no rates to show.</Empty>}
        {a.by_category.length > 0 && (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Category</th>
                  <th className="num">Sent</th>
                  <th className="num">Replied</th>
                  <th className="num">Hired</th>
                  <th className="num">Reply rate</th>
                  <th className="num">Hire rate</th>
                </tr>
              </thead>
              <tbody>
                {a.by_category.map((c) => (
                  <tr key={c.category}>
                    <td>{c.category}</td>
                    <td className="num">{c.submitted}</td>
                    <td className="num">{c.replied}</td>
                    <td className="num">{c.hired}</td>
                    <td className="num">{pct(c.reply_rate)}</td>
                    <td className="num">{pct(c.hire_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="card">
        <h2>Why jobs were not bid on</h2>
        {a.top_rejection_reasons.length === 0 && <Empty>No job has been skipped or rejected yet.</Empty>}
        <ul className="bars">
          {a.top_rejection_reasons.map(([reason, n]) => (
            <li key={String(reason)}>
              <span>{String(reason)}</span>
              <span className="bar" aria-hidden="true">
                <span style={{ width: Math.round((Number(n) / Number(a.top_rejection_reasons[0][1])) * 100) + "%" }} />
              </span>
              <strong>{String(n)}</strong>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
