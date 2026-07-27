"use client";

import { useAgentActivity } from "@/lib/hooks";
import type { AgentName } from "@/lib/types";

const AGENT_STYLE: Record<AgentName, { label: string; color: string }> = {
  diagnostic: { label: "Diagnostic", color: "var(--series-1)" },
  predictive: { label: "Predictive", color: "var(--series-4)" },
  recommend: { label: "Recommend", color: "var(--series-3)" },
  self_healing: { label: "Self-healing", color: "var(--series-2)" },
  sustainability: { label: "Sustainability", color: "var(--status-good)" },
  conversational: { label: "Assistant", color: "var(--text-secondary)" },
};

function formatTime(ts: { seconds: number } | undefined) {
  if (!ts) return "";
  return new Date(ts.seconds * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function AgentActivityLog({ assetId }: { assetId?: string }) {
  const events = useAgentActivity(assetId);

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Agent activity
        </h3>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          live tool calls, not simulated
        </span>
      </div>

      {events.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          No agent activity yet — it appears here the moment a scheduled sweep or chat message triggers a tool call.
        </p>
      ) : (
        <ul className="max-h-80 space-y-2 overflow-y-auto font-mono text-xs">
          {events.map((e) => {
            const style = AGENT_STYLE[e.agent] ?? { label: e.agent, color: "var(--text-muted)" };
            return (
              <li key={e.id} className="flex items-start gap-2">
                <span className="shrink-0" style={{ color: "var(--text-muted)" }}>
                  {formatTime(e.timestamp)}
                </span>
                <span className="shrink-0 font-semibold" style={{ color: style.color }}>
                  {style.label}
                </span>
                {!assetId && (
                  <span className="shrink-0" style={{ color: "var(--text-muted)" }}>
                    {e.asset_id}
                  </span>
                )}
                <span className="shrink-0" style={{ color: "var(--text-secondary)" }}>
                  {e.tool}
                </span>
                <span className="min-w-0 flex-1 truncate" style={{ color: "var(--text-primary)" }} title={e.summary}>
                  {e.summary}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
