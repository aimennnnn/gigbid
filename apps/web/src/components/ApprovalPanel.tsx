"use client";
import { useState } from "react";
import { api, ApiError } from "@/lib/client";
import { ErrorBox } from "./Bits";

/** Approve, edit or reject. Each choice resumes the paused graph thread through POST /approvals/{thread}. */
export function ApprovalPanel({ thread, draft, what, onDone }: { thread: string; draft: string; what: string; onDone: () => void }) {
  const [mode, setMode] = useState<"idle" | "edit" | "reject">("idle");
  const [text, setText] = useState(draft);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(body: { action: string; text?: string; reason?: string }) {
    setBusy(true);
    setError(null);
    try {
      await api(`/approvals/${encodeURIComponent(thread)}`, { json: body });
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not send your decision.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card approval" aria-label="Your decision">
      <h2>Your decision</h2>
      <p className="muted">Nothing is sent until you approve. {what}</p>
      <ErrorBox message={error} />
      {mode === "idle" && (
        <div className="row">
          <button className="primary" disabled={busy} onClick={() => send({ action: "approve" })} data-testid="approve">
            Approve and send
          </button>
          <button disabled={busy} onClick={() => setMode("edit")} data-testid="edit">
            Edit
          </button>
          <button className="danger" disabled={busy} onClick={() => setMode("reject")} data-testid="reject">
            Reject
          </button>
        </div>
      )}
      {mode === "edit" && (
        <>
          <label htmlFor="edit-text">Edit the text. It is checked against the policy again before it is sent.</label>
          <textarea id="edit-text" rows={10} value={text} onChange={(e) => setText(e.target.value)} data-testid="edit-text" />
          <div className="row">
            <button className="primary" disabled={busy || !text.trim()} onClick={() => send({ action: "edit", text })} data-testid="send-edit">
              Send my edited version
            </button>
            <button disabled={busy} onClick={() => setMode("idle")}>
              Cancel
            </button>
          </div>
        </>
      )}
      {mode === "reject" && (
        <>
          <label htmlFor="reject-reason">Why are you rejecting it? (required)</label>
          <input id="reject-reason" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="reject-reason" />
          <div className="row">
            <button className="danger" disabled={busy || !reason.trim()} onClick={() => send({ action: "reject", reason })} data-testid="confirm-reject">
              Reject this draft
            </button>
            <button disabled={busy} onClick={() => setMode("idle")}>
              Cancel
            </button>
          </div>
        </>
      )}
    </section>
  );
}
