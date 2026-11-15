"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ErrorBox, Status } from "@/components/Bits";
import { RunTimeline } from "@/components/RunTimeline";
import type { S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

export default function RunViewer() {
  const thread = decodeURIComponent(String(useParams().id));
  const { data: d, error, loading, reload } = useApi<S["RunDetail"]>(`/runs/${encodeURIComponent(thread)}`, 4000);
  if (loading && !d) return <p className="muted">Loading the run…</p>;
  if (!d) return <ErrorBox message={error ?? "Run not found."} />;
  return (
    <>
      <p>
        <Link href="/runs">← Runs</Link>
      </p>
      <div className="head">
        <h1>Agent run</h1>
        <Status status={d.status} />
      </div>
      <p className="muted">
        Trace id <code>{d.trace_id}</code> · {d.tokens.toLocaleString("en-US")} tokens
        {d.run.kind === "bid" && (
          <>
            {" "}
            · <Link href={`/jobs/${d.run.job_id}`}>Job {d.run.job_id}</Link>
          </>
        )}
      </p>
      <div className="cols wide">
        <section className="card">
          <h2>Steps, live</h2>
          <RunTimeline thread={thread} initial={d.events} running={d.run.running} onSettled={reload} />
        </section>
        <section className="card" id="trace">
          <h2>Trace: every tool call</h2>
          <p className="muted small">From the MCP servers&apos; audit logs, matched by the trace id. Emails and phone numbers are masked.</p>
          {d.trace.length === 0 && <p className="muted">No tool calls recorded yet.</p>}
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Server</th>
                  <th>Tool</th>
                  <th>Arguments</th>
                </tr>
              </thead>
              <tbody>
                {d.trace.map((t, i) => (
                  <tr key={i}>
                    <td>{t.server}</td>
                    <td>
                      <code>{t.tool}</code>
                    </td>
                    <td className="small">
                      <details>
                        <summary>{JSON.stringify(t.arguments).slice(0, 70)}</summary>
                        <pre>{JSON.stringify({ arguments: t.arguments, result: t.result }, null, 1).slice(0, 1500)}</pre>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </>
  );
}
