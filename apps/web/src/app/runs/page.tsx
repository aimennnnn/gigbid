"use client";
import Link from "next/link";
import { Empty, ErrorBox } from "@/components/Bits";
import type { S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

export default function Runs() {
  const { data, error, loading } = useApi<S["RunSummary"][]>("/runs", 4000);
  return (
    <>
      <div className="head">
        <h1>Agent runs</h1>
        <span className="muted">One run per job, and one per reply to a client.</span>
      </div>
      <ErrorBox message={error} />
      {loading && !data && <p className="muted">Loading…</p>}
      {data && data.length === 0 && <Empty>No runs yet. Analyse a job from the inbox to start one.</Empty>}
      {data && data.length > 0 && (
        <div className="scroll card">
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Kind</th>
                <th>Started</th>
                <th className="num">Steps</th>
                <th>State</th>
              </tr>
            </thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.thread_id}>
                  <td>
                    <Link href={`/runs/${encodeURIComponent(r.thread_id)}`}>{r.job_id || r.thread_id}</Link>
                  </td>
                  <td>{r.kind === "bid" ? "Job" : "Client reply"}</td>
                  <td>{new Date(r.started * 1000).toLocaleTimeString()}</td>
                  <td className="num">{r.steps}</td>
                  <td>{r.running ? "Running" : "Stopped"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
