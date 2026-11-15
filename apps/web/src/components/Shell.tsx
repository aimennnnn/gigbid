"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, saveSession, session, type S } from "@/lib/client";

const NAV = [
  ["/inbox", "Inbox"],
  ["/pipeline", "Pipeline"],
  ["/messages", "Messages"],
  ["/runs", "Runs"],
  ["/analytics", "Analytics"],
  ["/settings", "Settings"],
];

/** Page frame: sign-in guard, navigation, Connects balance and the degraded-mode banner. */
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [me, setMe] = useState<S["Me"] | null>(null);
  const [down, setDown] = useState(false);
  const open = path.startsWith("/login");

  useEffect(() => {
    const s = session();
    if (!s && !open) router.replace("/login");
    else if (s && !s.onboarded && !open && !path.startsWith("/onboarding")) router.replace("/onboarding");
    else setReady(true);
  }, [path, open, router]);

  useEffect(() => {
    const on = (e: Event) => setDown((e as CustomEvent<boolean>).detail);
    window.addEventListener("gigbid:degraded", on);
    return () => window.removeEventListener("gigbid:degraded", on);
  }, []);

  useEffect(() => {
    if (open || !session()) return;
    const check = () =>
      api<S["Health"]>("/health")
        .then((h) => setDown(h.marketplace !== "ok"))
        .catch(() => undefined);
    api<S["Me"]>("/me").then(setMe).catch(() => undefined);
    check();
    const t = setInterval(check, 8000);
    return () => clearInterval(t);
  }, [open, path]);

  if (!ready) return <main className="center muted">Loading…</main>;
  if (open) return <>{children}</>;
  return (
    <>
      <header className="top">
        <Link href="/inbox" className="brand">
          GigBid
        </Link>
        <nav aria-label="Main">
          {NAV.map(([href, label]) => (
            <Link key={href} href={href} className={path.startsWith(href) ? "on" : ""} aria-current={path.startsWith(href) ? "page" : undefined}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="who">
          {me && (
            <span className="muted" title="Connects left this week">
              {me.connects_balance ?? "-"} Connects
            </span>
          )}
          <span>{session()?.user}</span>
          <button
            className="link"
            onClick={() => {
              saveSession(null);
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </header>
      {down && (
        <div className="banner" role="alert" data-testid="degraded-banner">
          <strong>Marketplace unavailable.</strong> GigBid cannot reach the marketplace right now. Your drafts and pending approvals are safe;
          new jobs, sending and messages will work again when it is back.
        </div>
      )}
      <main className="page">{children}</main>
    </>
  );
}
