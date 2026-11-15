"use client";
import type { S } from "@/lib/client";

type Claim = { text: string; evidence_ids: string[]; status: string };
type Evidence = { id: string; title?: string; type?: string; text?: string };

/** The draft as text, with every claim highlighted. Hover or focus a claim to see the evidence behind it. */
export function EvidenceHover({ draft, claims, evidence }: { draft: string; claims: Claim[]; evidence: Record<string, Evidence> }) {
  const parts: { text: string; claim?: Claim }[] = [];
  let rest = draft;
  const found = claims
    .map((c) => ({ c, at: draft.indexOf(c.text) }))
    .filter((x) => x.at >= 0)
    .sort((a, b) => a.at - b.at);
  let offset = 0;
  for (const { c, at } of found) {
    if (at < offset) continue;
    parts.push({ text: draft.slice(offset, at) });
    parts.push({ text: c.text, claim: c });
    offset = at + c.text.length;
  }
  rest = draft.slice(offset);
  if (rest) parts.push({ text: rest });
  return (
    <p className="draft" data-testid="draft-view">
      {parts.map((p, i) =>
        p.claim ? (
          <span key={i} className={"claim " + p.claim.status} tabIndex={0} data-testid="claim">
            {p.text}
            <span className="tip" role="tooltip">
              <strong>{p.claim.status === "supported" ? "Supported by" : "Evidence"}</strong>
              {p.claim.evidence_ids.length === 0 && <span>No evidence attached.</span>}
              {p.claim.evidence_ids.map((id) => (
                <span key={id} className="ev">
                  <em>{evidence[id]?.title ?? id}</em>
                  {(evidence[id]?.text ?? "").replace(/[#*]/g, "").slice(0, 260)}
                </span>
              ))}
            </span>
          </span>
        ) : (
          <span key={i}>{p.text}</span>
        ),
      )}
    </p>
  );
}

export type StudioData = S["Studio"];
