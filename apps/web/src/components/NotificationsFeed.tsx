"use client";

import { useState } from "react";
import { useNotifications } from "@/lib/hooks";
import type { NotificationType } from "@/lib/types";

const TYPE_COLOR: Record<NotificationType, string> = {
  alert: "var(--status-serious)",
  resolved: "var(--status-good)",
  self_heal: "var(--series-1)",
  escalation: "var(--status-critical)",
  prediction: "var(--series-4)",
};

const FILTERS: Array<NotificationType | "all"> = ["all", "alert", "resolved", "self_heal", "escalation", "prediction"];

export function NotificationsFeed({ assetId }: { assetId?: string }) {
  const notifications = useNotifications(assetId);
  const [filter, setFilter] = useState<NotificationType | "all">("all");

  const filtered = filter === "all" ? notifications : notifications.filter((n) => n.type === filter);

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="rounded-full px-2.5 py-1 text-xs font-medium transition"
            style={{
              backgroundColor: filter === f ? "var(--series-1)" : "transparent",
              color: filter === f ? "#ffffff" : "var(--text-secondary)",
              border: `1px solid ${filter === f ? "var(--series-1)" : "var(--border)"}`,
            }}
          >
            {f.replaceAll("_", " ")}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          No notifications yet.
        </p>
      ) : (
        <ul className="space-y-2 max-h-96 overflow-y-auto">
          {filtered.map((n) => (
            <li key={n.id} className="flex items-start gap-2 text-sm">
              <span
                className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: TYPE_COLOR[n.type] }}
                aria-hidden="true"
              />
              <div>
                <p style={{ color: "var(--text-primary)" }}>{n.message}</p>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {n.asset_id} · {new Date(n.created_at.seconds * 1000).toLocaleString()}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
