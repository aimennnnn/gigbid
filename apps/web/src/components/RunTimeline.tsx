"use client";
import { useEffect, useRef, useState } from "react";
import { streamRun, type S } from "@/lib/client";

const NAME: Record<string, string> = {
  load_job: "Load the job post",
  analyst: "Job Analyst: read the post",
  risk: "Risk Assessor: check the client and the post",
  matcher: "Fit Matcher: find portfolio evidence",
  decide: "Decide: bid, watch or skip",
  pricing: "Pricing Strategist: set the price",
  writer: "Proposal Writer: draft",
  verifier: "Verifier: check every claim",
  critic: "Critic: review the draft",
  compliance: "Compliance Guard: policy check",
  recheck: "Compliance Guard: check your edit",
  preview: "Dry run: what would be sent",
  approval: "Waiting for your approval",
  learn_edit: "Learn from your edit",
  rejected: "Rejected by you",
  submit: "Submit to the marketplace",
  read: "Client Liaison: read the thread",
  draft: "Client Liaison: draft a reply",
  send: "Send the reply",
  end: "Stopped",
  error: "Error",
};

/** Node-by-node progress of a run, streamed live from the API (Server-Sent Events). */
export function RunTimeline({ thread, initial, running, onSettled }: { thread: string; initial: S["RunEvent"][]; running: boolean; onSettled?: () => void }) {
  const [steps, setSteps] = useState<S["RunEvent"][]>(initial);
  const [live, setLive] = useState(running);
  const settled = useRef(onSettled);
  settled.current = onSettled;

  useEffect(() => {
    setSteps(initial);
    setLive(running);
    if (!running) return;
    const stop = new AbortController();
    streamRun(thread, initial.length, (e) => setSteps((s) => (s.some((x) => x.seq === e.seq) ? s : [...s, e])), stop.signal)
      .catch(() => undefined)
      .finally(() => {
        if (!stop.signal.aborted) {
          setLive(false);
          settled.current?.();
        }
      });
    return () => stop.abort();
    // a new stream only when the run restarts, not on every refresh of `initial`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread, running]);

  const shown = steps.filter((s) => s.node !== "end");
  return (
    <ol className="timeline" aria-live="polite" data-testid="timeline">
      {shown.map((s) => (
        <li key={s.seq} className={s.errors?.length ? "failed" : s.waiting ? "waiting" : "done"}>
          <span className="dot" aria-hidden="true" />
          <span className="what">{NAME[s.node] ?? s.node}</span>
          <span className="muted">{s.seconds != null ? s.seconds.toFixed(1) + " s" : ""}</span>
          {s.tokens ? <span className="muted">{s.tokens.toLocaleString("en-US")} tokens</span> : null}
          {s.errors?.map((e, i) => (
            <span key={i} className="error">
              {e}
            </span>
          ))}
        </li>
      ))}
      {live && (
        <li className="running">
          <span className="dot" aria-hidden="true" />
          <span className="what">Working…</span>
        </li>
      )}
      {!live && shown.length === 0 && <li className="muted">No steps yet.</li>}
    </ol>
  );
}
