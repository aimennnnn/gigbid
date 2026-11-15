"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ErrorBox } from "@/components/Bits";
import { api, ApiError, saveSession, type SessionInfo } from "@/lib/client";

export default function Login() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api<SessionInfo>(`/auth/${mode}`, { json: { username, password } });
      saveSession(s);
      router.replace(s.onboarded ? "/inbox" : "/onboarding");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="center">
      <form className="card narrow" onSubmit={submit}>
        <h1>GigBid</h1>
        <p className="muted">Finds jobs that fit your portfolio and drafts proposals from real evidence. You approve everything it sends.</p>
        <ErrorBox message={error} />
        <label htmlFor="username">User name</label>
        <input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} required />
        <button className="primary" disabled={busy} data-testid="submit-auth">
          {mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button type="button" className="link" onClick={() => setMode(mode === "login" ? "signup" : "login")} data-testid="switch-auth">
          {mode === "login" ? "New here? Create an account" : "Have an account? Sign in"}
        </button>
      </form>
    </main>
  );
}
