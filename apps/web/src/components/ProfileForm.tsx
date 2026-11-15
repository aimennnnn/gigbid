"use client";
import { useEffect, useState } from "react";
import { ErrorBox } from "@/components/Bits";
import { api, ApiError, type S } from "@/lib/client";

export const PERSONAS: { id: "ml" | "web" | "data"; name: string; about: string }[] = [
  { id: "ml", name: "AI / ML engineer", about: "Models, NLP, RAG and agents" },
  { id: "web", name: "Full-stack web developer", about: "React, Next.js, APIs, payments" },
  { id: "data", name: "Data analyst", about: "Dashboards, SQL, reporting, statistics" },
];

export function ProfileForm({ submitLabel, onSaved }: { submitLabel: string; onSaved: (p: S["Profile"]) => void }) {
  const [p, setP] = useState<S["Profile"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<S["Me"]>("/me")
      .then((m) => setP(m.profile))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load your profile."));
  }, []);
  if (!p) return error ? <ErrorBox message={error} /> : <p className="muted">Loading…</p>;
  const set = (changes: Partial<S["Profile"]>) => setP({ ...p, ...changes });

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!p) return;
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<S["Profile"]>("/me/profile", { method: "PUT", json: p }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="stack">
      <ErrorBox message={error} />
      <fieldset>
        <legend>Which portfolio should GigBid use?</legend>
        <div className="choices">
          {PERSONAS.map((x) => (
            <label key={x.id} className={"choice" + (p.persona === x.id ? " on" : "")}>
              <input type="radio" name="persona" checked={p.persona === x.id} onChange={() => set({ persona: x.id })} data-testid={"persona-" + x.id} />
              <strong>{x.name}</strong>
              <span className="muted">{x.about}</span>
            </label>
          ))}
        </div>
        <p className="muted small">These are the three sample portfolios (synthetic). Uploading your own portfolio is not built yet.</p>
      </fieldset>
      <div className="grid2">
        <div>
          <label htmlFor="floor">Lowest budget you accept (USD)</label>
          <input id="floor" type="number" min={0} value={p.min_budget ?? 0} onChange={(e) => set({ min_budget: Number(e.target.value) })} />
        </div>
        <div>
          <label htmlFor="connects">Weekly Connects budget</label>
          <input id="connects" type="number" min={0} value={p.weekly_connects_budget ?? 0} onChange={(e) => set({ weekly_connects_budget: Number(e.target.value) })} />
        </div>
      </div>
      <fieldset>
        <legend>Show jobs in these categories (none ticked = all)</legend>
        <div className="row">
          {PERSONAS.map((x) => (
            <label key={x.id} className="check">
              <input
                type="checkbox"
                checked={(p.categories ?? []).includes(x.id)}
                onChange={(e) => set({ categories: e.target.checked ? [...(p.categories ?? []), x.id] : (p.categories ?? []).filter((c) => c !== x.id) })}
              />
              {x.name}
            </label>
          ))}
        </div>
      </fieldset>
      <p className="muted small">Marketplace: GigSim (the course simulator), connected as your own account. Live Upwork is not connected in this build.</p>
      <button className="primary" disabled={busy || !p.persona} data-testid="save-profile">
        {submitLabel}
      </button>
    </form>
  );
}
