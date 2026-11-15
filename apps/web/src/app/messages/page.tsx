"use client";
import { useState } from "react";
import { ApprovalPanel } from "@/components/ApprovalPanel";
import { Empty, ErrorBox } from "@/components/Bits";
import { api, ApiError, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

const INTENT: Record<string, string> = {
  interview_request: "The client wants a call",
  negotiation: "The client is negotiating the price",
  question: "The client asked a question",
  scam_signal: "Warning: the client asked to move off the platform",
  other: "Message",
};

export default function Messages() {
  const { data, error, loading, reload } = useApi<S["Conversations"]>("/messages", 4000);
  const [note, setNote] = useState<string | null>(null);

  async function suggest(thread: string) {
    setNote(null);
    try {
      await api(`/messages/${encodeURIComponent(thread)}/suggest`, { method: "POST" });
      await reload();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Could not draft a reply.");
    }
  }

  return (
    <>
      <div className="head">
        <h1>Messages</h1>
        <span className="muted">Replies are drafted for you and sent only after you approve.</span>
      </div>
      <ErrorBox message={note ?? error} />
      {loading && !data && <p className="muted">Loading…</p>}
      {data && data.threads.length === 0 && <Empty>No client has replied yet. When one does, the thread shows up here.</Empty>}
      <div className="stack">
        {data?.threads.map((t) => (
          <section key={t.thread_id} className="card" data-testid="thread">
            <h2>{t.title}</h2>
            <ol className="chat">
              {t.messages.map((m, i) => (
                <li key={i} className={m.sender}>
                  <small>{m.sender === "client" ? "Client" : "You"}</small>
                  {m.text}
                </li>
              ))}
            </ol>
            {t.needs_reply && !t.suggested && (
              <button className="primary" onClick={() => suggest(t.thread_id)} data-testid="suggest">
                Suggest a reply
              </button>
            )}
            {t.suggested?.running && <p className="muted">Drafting a reply…</p>}
            {t.suggested && !t.suggested.running && (
              <>
                {t.suggested.intent && <p className={"notice" + (t.suggested.intent === "scam_signal" ? " bad" : "")}>{INTENT[t.suggested.intent] ?? t.suggested.intent}</p>}
                <ErrorBox message={t.suggested.errors.length ? t.suggested.errors.join(" · ") : null} />
                {t.suggested.draft && (
                  <>
                    <h3>Suggested reply</h3>
                    <p className="draft">{t.suggested.draft}</p>
                    {(t.suggested.interview_slots ?? []).length > 0 && <p className="muted">Call times offered: {(t.suggested.interview_slots ?? []).join(", ")}</p>}
                  </>
                )}
                {t.suggested.pending && t.suggested.draft && (
                  <ApprovalPanel thread={t.suggested.thread_id} draft={t.suggested.draft} what="Approving sends this reply to the client." onDone={reload} />
                )}
              </>
            )}
            {!t.needs_reply && <p className="muted small">Waiting for the client.</p>}
          </section>
        ))}
      </div>
    </>
  );
}
