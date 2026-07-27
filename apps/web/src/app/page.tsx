"use client";

import { useAssets } from "@/lib/hooks";
import { AssetCard } from "@/components/AssetCard";
import { NotificationsFeed } from "@/components/NotificationsFeed";
import { AgentActivityLog } from "@/components/AgentActivityLog";
import { DeliverablesPanel } from "@/components/DeliverablesPanel";

export default function FleetOverviewPage() {
  const { assets, loading } = useAssets();

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Fleet overview
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Live health, diagnostics, and self-healing across your connected fleet.
        </p>
      </header>

      <div className="space-y-10">
        <DeliverablesPanel />

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Assets
          </h2>
          {loading ? (
            <p style={{ color: "var(--text-muted)" }}>Loading assets…</p>
          ) : assets.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>
              No assets yet — start the simulator or register an asset via the API.
            </p>
          ) : (
            <div className="space-y-4">
              {assets.map((asset) => (
                <AssetCard key={asset.id} asset={asset} />
              ))}
            </div>
          )}
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Agent activity (fleet-wide)
          </h2>
          <AgentActivityLog />
        </section>

        <section className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-secondary)" }}>
            Notifications
          </h2>
          <NotificationsFeed />
        </section>
      </div>
    </main>
  );
}
