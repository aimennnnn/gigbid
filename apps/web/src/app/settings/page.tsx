"use client";
import { useState } from "react";
import { Empty, ErrorBox } from "@/components/Bits";
import { ProfileForm } from "@/components/ProfileForm";
import { api, ApiError, type S } from "@/lib/client";
import { useApi } from "@/lib/hooks";

export default function Settings() {
  const memory = useApi<S["Memories"]>("/memory");
  const health = useApi<S["Health"]>("/health");
  const [saved, setSaved] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  async function forget(m: S["Memory"]) {
    try {
      await api(`/memory/${m.kind}/${encodeURIComponent(m.key)}`, { method: "DELETE" });
      await memory.reload();
    } catch (e) {
      setNote(e instanceof ApiError ? e.message : "Could not delete it.");
    }
  }

  return (
    <>
      <div className="head">
        <h1>Settings</h1>
      </div>
      <section className="card">
        <h2>Profile, budgets and filters</h2>
        <ProfileForm submitLabel="Save settings" onSaved={() => setSaved(true)} />
        {saved && (
          <p className="notice ok" role="status">
            Saved.
          </p>
        )}
      </section>
      <section className="card">
        <h2>Autonomy</h2>
        <p>
          <strong>You approve everything that is sent.</strong> GigBid may skip low-fit jobs on its own, but it can never send a proposal or a message without your approval. This cannot be turned
          off.
        </p>
      </section>
      <section className="card">
        <h2>Connected accounts</h2>
        <p>
          GigSim: {health.data ? (health.data.marketplace === "ok" ? "connected" : "not reachable right now") : "checking…"} · Model: {health.data?.llm ?? "…"}
        </p>
      </section>
      <section className="card">
        <h2>What GigBid has learned about you</h2>
        <p className="muted small">Style rules come from your own edits (after the same kind of edit twice). Outcome counts come from marketplace events. Delete anything you do not want it to use.</p>
        <ErrorBox message={note ?? memory.error} />
        {memory.data && memory.data.items.length === 0 && <Empty>Nothing learned yet.</Empty>}
        <ul className="memory" data-testid="memory">
          {memory.data?.items.map((m) => (
            <li key={m.kind + m.key}>
              <span>{m.text}</span>
              <button className="danger" onClick={() => forget(m)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
