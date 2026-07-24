import type { AssetStatus, IssueState, Severity } from "@/lib/types";

const ASSET_STATUS_MAP: Record<AssetStatus, { label: string; color: string; icon: string }> = {
  healthy: { label: "Healthy", color: "var(--status-good)", icon: "✓" },
  warning: { label: "Warning", color: "var(--status-warning)", icon: "⚠" },
  critical: { label: "Critical", color: "var(--status-critical)", icon: "✕" },
};

const ISSUE_STATE_MAP: Record<IssueState, { label: string; color: string; icon: string }> = {
  NEW: { label: "New", color: "var(--status-warning)", icon: "●" },
  OPEN: { label: "Open", color: "var(--status-serious)", icon: "⚠" },
  MONITORING: { label: "Monitoring", color: "var(--series-1)", icon: "◔" },
  RESOLVED: { label: "Resolved", color: "var(--status-good)", icon: "✓" },
  ESCALATED: { label: "Escalated", color: "var(--status-critical)", icon: "✕" },
};

const SEVERITY_MAP: Record<Severity, { label: string; color: string }> = {
  low: { label: "Low", color: "var(--status-good)" },
  medium: { label: "Medium", color: "var(--status-warning)" },
  high: { label: "High", color: "var(--status-critical)" },
};

function Badge({ label, color, icon }: { label: string; color: string; icon?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{ color, backgroundColor: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      {icon && <span aria-hidden="true">{icon}</span>}
      {label}
    </span>
  );
}

export function AssetStatusBadge({ status }: { status: AssetStatus }) {
  const cfg = ASSET_STATUS_MAP[status];
  return <Badge label={cfg.label} color={cfg.color} icon={cfg.icon} />;
}

export function IssueStateBadge({ state }: { state: IssueState }) {
  const cfg = ISSUE_STATE_MAP[state];
  return <Badge label={cfg.label} color={cfg.color} icon={cfg.icon} />;
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const cfg = SEVERITY_MAP[severity];
  return <Badge label={cfg.label} color={cfg.color} />;
}
