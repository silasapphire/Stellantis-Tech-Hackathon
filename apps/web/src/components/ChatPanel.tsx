"use client";

import { useEffect, useRef, useState } from "react";
import { WS_BASE } from "@/lib/api";
import type { Asset } from "@/lib/types";

type Entry =
  | { kind: "user" | "assistant" | "error"; content: string }
  | { kind: "tool"; tool: string; args: Record<string, unknown> };

const SUGGESTIONS = (a: Asset) => [
  `Why is ${a.id} flagged?`,
  "Will it fail soon?",
  "What does the repair knowledge say?",
  "Can you run the self-heal?",
];

export function ChatPanel({ asset }: { asset: Asset }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [pending, setPending] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${asset.id}`);
    wsRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const d = JSON.parse(event.data);
      if (d.type === "tool_call") setEntries((p) => [...p, { kind: "tool", tool: d.tool, args: d.args }]);
      else if (d.type === "final") { setPending(false); setEntries((p) => [...p, { kind: "assistant", content: d.content }]); }
      else if (d.type === "error") { setPending(false); setEntries((p) => [...p, { kind: "error", content: d.content }]); }
    };
    return () => ws.close();
  }, [asset.id]);

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" }); }, [entries, pending]);

  function send(text: string) {
    const msg = text.trim();
    const ws = wsRef.current;
    if (!msg || !ws || ws.readyState !== WebSocket.OPEN || pending) return;
    setEntries((p) => [...p, { kind: "user", content: msg }]);
    ws.send(msg);
    setInput("");
    setPending(true);
  }

  return (
    <section className="flex h-full min-h-[480px] flex-col rounded-xl border" style={{ background: "var(--panel)", borderColor: "var(--line)" }}>
      <header className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
        <h3 className="flex items-center gap-2 text-sm font-semibold"><span style={{ color: "var(--blue)" }}>💬</span> Agentic AI Chat</h3>
        <span className="flex items-center gap-1.5 text-[11px]" style={{ color: connected ? "var(--green)" : "var(--faint)" }}>
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: connected ? "var(--green)" : "var(--faint)" }} />{connected ? asset.id : "connecting…"}
        </span>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3" aria-live="polite">
        {entries.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm" style={{ color: "var(--muted)" }}>Ask about {asset.id}. The assistant calls MCP tools (telemetry, twin, diagnostics, RAG, actions) and cites their results.</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS(asset).map((s) => (
                <button key={s} onClick={() => send(s)} className="rounded-full border px-3 py-1 text-xs" style={{ borderColor: "var(--line)", background: "var(--panel-2)", color: "var(--text)" }}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {entries.map((e, i) => {
          if (e.kind === "tool")
            return <div key={i} className="font-mono text-[11px]" style={{ color: "var(--faint)" }}>⚙ {e.tool}{Object.keys(e.args).length ? ` ${JSON.stringify(e.args)}` : ""}</div>;
          if (e.kind === "error")
            return <div key={i} className="rounded-md px-3 py-2 text-xs" style={{ background: "color-mix(in srgb, var(--red) 14%, transparent)", color: "#ffb4b4" }}>{e.content}</div>;
          const user = e.kind === "user";
          return (
            <div key={i} className={`flex ${user ? "justify-end" : "justify-start"}`}>
              <div className="max-w-[88%] whitespace-pre-wrap rounded-xl px-3 py-2 text-[13px] leading-relaxed"
                style={{ background: user ? "var(--blue)" : "var(--panel-2)", color: user ? "#fff" : "var(--text)", border: user ? "none" : "1px solid var(--line)" }}>
                {e.content}
              </div>
            </div>
          );
        })}
        {pending && <div className="text-xs" style={{ color: "var(--faint)" }}>thinking…</div>}
      </div>

      <form className="flex gap-2 border-t p-3" style={{ borderColor: "var(--line)" }} onSubmit={(ev) => { ev.preventDefault(); send(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about any asset, diagnostic, or repair…" aria-label="Message"
          className="min-w-0 flex-1 rounded-md border px-3 py-2 text-sm outline-none" style={{ background: "var(--panel-2)", borderColor: "var(--line)", color: "var(--text)" }} />
        <button type="submit" disabled={!connected || pending} aria-label="Send" className="rounded-md px-3 text-white disabled:opacity-40" style={{ background: "var(--blue)" }}>➤</button>
      </form>
    </section>
  );
}
