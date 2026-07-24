"use client";

import Link from "next/link";
import { useAsset } from "@/lib/hooks";
import { AssetStatusBadge } from "./StatusBadge";
import { AssetTelemetryCharts } from "./AssetTelemetryCharts";
import { IssueTimeline } from "./IssueTimeline";
import { ChatPanel } from "./ChatPanel";
import { SustainabilityPanel } from "./SustainabilityPanel";
import { NotificationsFeed } from "./NotificationsFeed";

export function AssetDetailClient({ assetId }: { assetId: string }) {
  const asset = useAsset(assetId);

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
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

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section className="space-y-6">
          {asset && <AssetTelemetryCharts assetId={assetId} vehicleType={asset.vehicle_type} />}

          <div>
            <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Issue timeline
            </h2>
            <IssueTimeline assetId={assetId} />
          </div>

          <div>
            <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Sustainability
            </h2>
            <SustainabilityPanel assetId={assetId} />
          </div>
        </section>

        <aside className="space-y-6">
          <ChatPanel assetId={assetId} />
          <div>
            <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              Notifications
            </h2>
            <NotificationsFeed assetId={assetId} />
          </div>
        </aside>
      </div>
    </main>
  );
}
