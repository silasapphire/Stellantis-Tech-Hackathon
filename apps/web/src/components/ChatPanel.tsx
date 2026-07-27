"use client";

import { useEffect, useRef, useState } from "react";

type ChatEntry =
  | { kind: "user" | "assistant" | "error"; content: string }
  | { kind: "tool_call"; tool: string; args: Record<string, unknown> };

const WS_BASE = process.env.NEXT_PUBLIC_API_WS_URL ?? "ws://localhost:8000";

export function ChatPanel({ assetId }: { assetId: string }) {
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [input, setInput] = useState("");
  const [connected, setConnected] = useState(false);
  const [pending, setPending] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/ws/chat/${assetId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "tool_call") {
        setEntries((prev) => [...prev, { kind: "tool_call", tool: data.tool, args: data.args }]);
      } else if (data.type === "final") {
        setPending(false);
        setEntries((prev) => [...prev, { kind: "assistant", content: data.content }]);
      } else if (data.type === "error") {
        setPending(false);
        setEntries((prev) => [...prev, { kind: "error", content: data.content }]);
      }
    };

    return () => ws.close();
  }, [assetId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [entries]);

  function send() {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    setEntries((prev) => [...prev, { kind: "user", content: input }]);
    wsRef.current.send(input);
    setInput("");
    setPending(true);
  }

  return (
    <div className="flex h-[520px] flex-col rounded-xl" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between border-b px-4 py-2.5" style={{ borderColor: "var(--gridline)" }}>
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Assistant
        </h3>
        <span
          className="flex items-center gap-1.5 text-xs"
          style={{ color: connected ? "var(--status-good-text)" : "var(--text-muted)" }}
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: connected ? "var(--status-good)" : "var(--text-muted)" }}
          />
          {connected ? "connected" : "connecting…"}
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-2 overflow-y-auto px-4 py-3">
        {entries.length === 0 && (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            Ask about this asset — e.g. &ldquo;Why is this flagged?&rdquo;, &ldquo;Will it fail soon?&rdquo;, or &ldquo;Fix it&rdquo;.
          </p>
        )}
        {entries.map((entry, i) => {
          if (entry.kind === "tool_call") {
            return (
              <div key={i} className="text-xs italic" style={{ color: "var(--text-muted)" }}>
                calling <code className="font-mono not-italic">{entry.tool}</code>
                {Object.keys(entry.args).length > 0 && (
                  <span className="font-mono"> {JSON.stringify(entry.args)}</span>
                )}
                …
              </div>
            );
          }
          if (entry.kind === "error") {
            return (
              <div
                key={i}
                className="rounded-md px-3 py-2 text-center text-xs"
                style={{ backgroundColor: "color-mix(in srgb, var(--status-critical) 12%, transparent)", color: "var(--status-critical)" }}
              >
                {entry.content}
              </div>
            );
          }
          const isUser = entry.kind === "user";
          return (
            <div key={i} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
              <div
                className="max-w-[85%] rounded-lg px-3 py-2 text-sm"
                style={{
                  backgroundColor: isUser ? "var(--series-1)" : "var(--page-plane)",
                  color: isUser ? "#ffffff" : "var(--text-primary)",
                }}
              >
                {entry.content}
              </div>
            </div>
          );
        })}
        {pending && (
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            thinking…
          </div>
        )}
      </div>

      <div className="flex gap-2 border-t p-3" style={{ borderColor: "var(--gridline)" }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask a question…"
          className="flex-1 rounded-md px-3 py-2 text-sm outline-none"
          style={{ backgroundColor: "var(--page-plane)", color: "var(--text-primary)", border: "1px solid var(--border)" }}
        />
        <button
          onClick={send}
          disabled={!connected}
          className="rounded-md px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          style={{ backgroundColor: "var(--series-1)" }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
