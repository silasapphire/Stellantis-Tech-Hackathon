"use client";

import { useIssues } from "@/lib/hooks";
import { ConfidenceBadge, IssueStateBadge, SeverityBadge } from "./StatusBadge";

function formatTime(ts: { seconds: number } | string | undefined) {
  if (!ts) return "";
  const date = typeof ts === "string" ? new Date(ts) : new Date(ts.seconds * 1000);
  return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function IssueTimeline({ assetId }: { assetId: string }) {
  const issues = useIssues(assetId);

  if (issues.length === 0) {
    return (
      <div className="rounded-xl p-6 text-sm" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
        No issues detected for this asset.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {issues.map((issue) => (
        <div key={issue.id} className="rounded-xl p-4" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <IssueStateBadge state={issue.state} />
              <SeverityBadge severity={issue.severity} />
              <ConfidenceBadge confidence={issue.confidence ?? 1} />
              <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                {issue.type.replaceAll("_", " ")}
              </span>
            </div>
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              detected {formatTime(issue.detected_at)}
            </span>
          </div>

          {issue.explanation && (
            <p className="mt-2 text-sm" style={{ color: "var(--text-secondary)" }}>
              {issue.explanation}
            </p>
          )}
          {issue.recommendation && (
            <p className="mt-1.5 text-sm" style={{ color: "var(--text-primary)" }}>
              <span className="font-medium">Recommendation: </span>
              {issue.recommendation}
            </p>
          )}
          {issue.self_heal_action && (
            <p className="mt-1.5 text-xs" style={{ color: "var(--text-muted)" }}>
              Self-heal: {issue.self_heal_action} · {issue.self_heal_attempts} attempt(s)
            </p>
          )}

          <ol className="mt-3 space-y-1.5 border-l pl-3" style={{ borderColor: "var(--gridline)" }}>
            {issue.history.map((entry, i) => (
              <li key={i} className="text-xs" style={{ color: "var(--text-secondary)" }}>
                <span className="font-medium" style={{ color: "var(--text-primary)" }}>
                  {entry.state}
                </span>{" "}
                — {entry.note}{" "}
                <span style={{ color: "var(--text-muted)" }}>
                  ({entry.agent}, {formatTime(entry.timestamp)})
                </span>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
