"use client";
import { pct } from "@/lib/client";

const FLAG: Record<string, string> = {
  scam: "Scam signs",
  free_work: "Asks for free work",
  off_platform: "Off-platform contact",
  prompt_injection: "Hidden instructions",
  new_client: "New client",
  low_hire_rate: "Rarely hires",
  unverified_payment: "Payment not verified",
  vague_scope: "Vague scope",
};
const BAD = new Set(["scam", "free_work", "off_platform", "prompt_injection"]);

export function RiskBadges({ flags }: { flags: string[] }) {
  if (!flags.length) return <span className="badge ok">No risk flags</span>;
  return (
    <span className="badges">
      {flags.map((f) => (
        <span key={f} className={"badge " + (BAD.has(f) ? "bad" : "warn")}>
          {FLAG[f] ?? f}
        </span>
      ))}
    </span>
  );
}

export function Fit({ value }: { value?: number | null }) {
  if (value == null) return <span className="muted">-</span>;
  return (
    <span className="fit" title={"Fit " + pct(value)}>
      <span className="bar" aria-hidden="true">
        <span style={{ width: pct(value) }} />
      </span>
      {pct(value)}
    </span>
  );
}

export function Action({ action }: { action?: string | null }) {
  if (!action) return <span className="muted">-</span>;
  return <span className={"pill " + action}>{action === "bid" ? "Bid" : action === "watch" ? "Watch" : "Skip"}</span>;
}

export function Status({ status }: { status?: string | null }) {
  const label: Record<string, string> = {
    analysing: "Analysing",
    skipped: "Skipped",
    watching: "Watching",
    drafting: "Drafting",
    awaiting_approval: "Needs your approval",
    submitted: "Submitted",
    rejected: "Rejected by you",
    needs_attention: "Needs attention",
    dead_letter: "Could not finish",
  };
  return <span className={"status " + (status ?? "")}>{status ? (label[status] ?? status) : "Not analysed"}</span>;
}

export function ErrorBox({ message }: { message: string | null }) {
  return message ? (
    <p className="error" role="alert">
      {message}
    </p>
  ) : null;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="empty">{children}</p>;
}
