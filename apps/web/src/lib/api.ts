"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const WS_BASE = process.env.NEXT_PUBLIC_API_WS_URL ?? API_BASE.replace(/^http/, "ws");

/**
 * Poll a JSON endpoint. Replaces the old Firestore realtime listeners: the API is the only
 * data source now. Pass `null` to pause. Keeps the last good value if a poll fails.
 */
export function useApi<T>(path: string | null, intervalMs = 3000) {
  const [store, setStore] = useState<{ path: string | null; data: T | null }>({ path: null, data: null });
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = (await res.json()) as T;
      if (alive.current) {
        setStore({ path, data: json });
        setError(null);
        setUpdatedAt(Date.now());
      }
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : String(e));
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    const first = setTimeout(load, 0);
    const id = path && intervalMs > 0 ? setInterval(load, intervalMs) : undefined;
    return () => {
      alive.current = false;
      clearTimeout(first);
      if (id) clearInterval(id);
    };
  }, [path, intervalMs, load]);

  // data from a previous path is never returned for the current one (e.g. after switching asset)
  const data = store.path === path ? store.data : null;
  return { data, error, updatedAt, reload: load };
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((json as { detail?: string }).detail ?? `${res.status}`);
  return json as T;
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "—";
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}
