"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./client";

/** Load something from the API, with loading and error states, and an optional refresh interval. */
export function useApi<T>(path: string | null, everyMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const load = useCallback(async () => {
    if (!path) return;
    try {
      const d = await api<T>(path);
      if (alive.current) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      if (alive.current) setError(e instanceof ApiError ? e.message : "Something went wrong.");
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    alive.current = true;
    load();
    const t = everyMs ? setInterval(load, everyMs) : null;
    return () => {
      alive.current = false;
      if (t) clearInterval(t);
    };
  }, [load, everyMs]);
  return { data, error, loading, reload: load };
}
