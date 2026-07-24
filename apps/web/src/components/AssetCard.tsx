import Link from "next/link";
import type { Asset } from "@/lib/types";
import { AssetStatusBadge } from "./StatusBadge";

const VEHICLE_ICON: Record<Asset["vehicle_type"], string> = { EV: "⚡", ICE: "⛽" };

export function AssetCard({ asset }: { asset: Asset }) {
  const riskPct = Math.max(0, Math.min(100, asset.risk_score_numeric));
  const riskColor =
    asset.risk_score === "high"
      ? "var(--status-critical)"
      : asset.risk_score === "medium"
        ? "var(--status-warning)"
        : "var(--status-good)";

  return (
    <Link
      href={`/assets/${asset.id}`}
      className="block rounded-xl p-5 transition hover:-translate-y-0.5"
      style={{
        backgroundColor: "var(--surface-1)",
        border: "1px solid var(--border)",
      }}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            <span aria-hidden="true">{VEHICLE_ICON[asset.vehicle_type]}</span>
            {asset.name}
          </div>
          <div className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>
            {asset.vehicle_type} · {asset.id}
          </div>
        </div>
        <AssetStatusBadge status={asset.status} />
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-xs" style={{ color: "var(--text-secondary)" }}>
          <span>Risk score</span>
          <span className="font-medium" style={{ color: riskColor }}>
            {asset.risk_score} · {riskPct.toFixed(0)}
          </span>
        </div>
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full" style={{ backgroundColor: "var(--gridline)" }}>
          <div className="h-full rounded-full" style={{ width: `${riskPct}%`, backgroundColor: riskColor }} />
        </div>
      </div>
    </Link>
  );
}
