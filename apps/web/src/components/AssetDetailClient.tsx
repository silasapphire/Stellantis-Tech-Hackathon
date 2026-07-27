"use client";

import Link from "next/link";
import { useAsset } from "@/lib/hooks";
import { AssetStatusBadge } from "./StatusBadge";
import { LiveReadings } from "./LiveReadings";
import { AssetTelemetryCharts } from "./AssetTelemetryCharts";
import { IssueTimeline } from "./IssueTimeline";
import { AgentActivityLog } from "./AgentActivityLog";
import { ChatPanel } from "./ChatPanel";
import { SustainabilityPanel } from "./SustainabilityPanel";
import { NotificationsFeed } from "./NotificationsFeed";

export function AssetDetailClient({ assetId }: { assetId: string }) {
  const asset = useAsset(assetId);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <Link href="/" className="text-sm" style={{ color: "var(--series-1)" }}>
        ← Fleet overview
      </Link>

      <header className="mt-3 mb-8 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
            {asset?.name ?? assetId}
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
            {asset?.vehicle_type ?? "—"} · risk: {asset?.risk_score ?? "—"} ({asset?.risk_score_numeric.toFixed(0) ?? "—"})
          </p>
        </div>
        {asset && <AssetStatusBadge status={asset.status} />}
      </header>

      <div className="space-y-10">
        {asset && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
              Live readings
            </h2>
            <LiveReadings assetId={assetId} vehicleType={asset.vehicle_type} />
          </section>
        )}

        {asset && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
              Telemetry
            </h2>
            <AssetTelemetryCharts assetId={assetId} vehicleType={asset.vehicle_type} />
          </section>
        )}

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Issue timeline
          </h2>
          <IssueTimeline assetId={assetId} />
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Agent activity
          </h2>
          <AgentActivityLog assetId={assetId} />
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Ask AI
          </h2>
          <ChatPanel assetId={assetId} />
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Sustainability
          </h2>
          <SustainabilityPanel assetId={assetId} />
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Notifications
          </h2>
          <NotificationsFeed assetId={assetId} />
        </section>
      </div>
    </main>
  );
}
