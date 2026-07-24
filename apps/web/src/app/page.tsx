"use client";

import { useAssets } from "@/lib/hooks";
import { AssetCard } from "@/components/AssetCard";
import { NotificationsFeed } from "@/components/NotificationsFeed";

export default function FleetOverviewPage() {
  const { assets, loading } = useAssets();

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Fleet overview
        </h1>
        <p className="mt-1 text-sm" style={{ color: "var(--text-secondary)" }}>
          Smart Connected Diagnostics Platform
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <section>
          {loading ? (
            <p style={{ color: "var(--text-muted)" }}>Loading assets…</p>
          ) : assets.length === 0 ? (
            <p style={{ color: "var(--text-muted)" }}>
              No assets yet — start the simulator or register an asset via the API.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {assets.map((asset) => (
                <AssetCard key={asset.id} asset={asset} />
              ))}
            </div>
          )}
        </section>

        <aside>
          <h2 className="mb-3 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Notifications
          </h2>
          <NotificationsFeed />
        </aside>
      </div>
    </main>
  );
}
