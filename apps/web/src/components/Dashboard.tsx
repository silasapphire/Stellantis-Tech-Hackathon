"use client";

import { useMemo, useState } from "react";
import { API_BASE, ago, useApi } from "@/lib/api";
import type { AppNotification, Asset, Issue, KbMatch, ServiceHealth, Stats, TwinResponse } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import {
  ActivityPanel, ArchitecturePanel, AssetHeader, FaultControl, FleetList, IssuesList, KpiRow, McpPanel, NotificationsList,
  PipelinePanel, RagPanel, SystemHealthCard, TelemetryPanel, TwinPanel, healthColor, healthOf,
} from "./panels";
import { Card, Empty, Pill, humanize } from "./ui";

const NAV = [
  ["overview", "Overview", "⌂"], ["fleet", "Fleet / Assets", "🚘"], ["telemetry", "Telemetry", "〰"], ["twin", "Digital Twin", "◎"],
  ["diagnostics", "AI Diagnostics", "✦"], ["workflow", "Agent Workflow", "⛓"], ["mcp", "MCP Tools", "🔌"], ["kb", "Knowledge Base (RAG)", "📖"],
  ["alerts", "Alerts & Issues", "🔔"], ["healing", "Self-Healing", "🛠"], ["system", "System Monitor", "📈"], ["settings", "Settings", "⚙"],
] as const;
type View = (typeof NAV)[number][0];

export function Dashboard() {
  const [view, setView] = useState<View>("overview");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const assets = useApi<Asset[]>("/assets?with_latest=true", 3000);
  const stats = useApi<Stats>("/stats", 4000);
  const health = useApi<ServiceHealth[]>("/system/health", 6000);
  const issues = useApi<Issue[]>("/issues?limit=100", 3000);
  const list = useMemo(() => assets.data ?? [], [assets.data]);

  // default selection: the first asset with an issue, else the first asset
  const asset = list.find((a) => a.id === selectedId) ?? list.find((a) => a.status !== "healthy") ?? list[0] ?? null;
  const twin = useApi<TwinResponse>(asset ? `/assets/${asset.id}/twin` : null, 4000);
  const connected = !assets.error && assets.data !== null;
  const unresolved = stats.data?.active_alerts.count ?? 0;

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[232px_1fr]">
      {/* sidebar */}
      <aside className="flex flex-col gap-4 border-r p-4 lg:sticky lg:top-0 lg:h-screen" style={{ borderColor: "var(--line)", background: "color-mix(in srgb, var(--panel) 70%, var(--bg))" }}>
        <div className="px-1 pt-1 text-center">
          <div className="text-[15px] font-light tracking-[0.35em]" style={{ color: "var(--text)" }}>STELLANTIS</div>
          <div className="mt-2 text-[15px] font-semibold leading-tight">Smart Connected<br />Diagnostics Platform</div>
        </div>
        <nav aria-label="Sections" className="flex-1 overflow-y-auto">
          <ul className="space-y-0.5">
            {NAV.map(([key, label, icon]) => (
              <li key={key}>
                <button onClick={() => setView(key)} aria-current={view === key ? "page" : undefined}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-[13px]"
                  style={{ background: view === key ? "color-mix(in srgb, var(--blue) 22%, transparent)" : "transparent", color: view === key ? "var(--text)" : "var(--muted)" }}>
                  <span className="w-5 text-center" aria-hidden>{icon}</span>{label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <SystemHealthCard health={health.data} />
      </aside>

      {/* main */}
      <div className="min-w-0 p-4 lg:p-5">
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Smart Connected Diagnostics Platform</h1>
            <p className="text-sm" style={{ color: "var(--muted)" }}>Engine / Fleet Health Digital Twin · Agentic AI (LangGraph) · RAG · MCP Tools</p>
          </div>
          <div className="flex items-center gap-3">
            <Pill color={connected ? "var(--green)" : "var(--red)"} className="!px-3 !py-1.5 !text-xs"><span className={`h-2 w-2 rounded-full ${connected ? "pulse-dot" : ""}`} style={{ background: connected ? "var(--green)" : "var(--red)" }} /> {connected ? "Live" : "API offline"}</Pill>
            <span className="text-xs" style={{ color: "var(--muted)" }}>Last update: {assets.updatedAt ? ago(new Date(assets.updatedAt).toISOString()) : "—"}</span>
            <button onClick={() => setView("alerts")} className="relative grid h-9 w-9 place-items-center rounded-full border" style={{ borderColor: "var(--line)", background: "var(--panel)" }} aria-label={`${unresolved} active alerts`}>
              🔔{unresolved > 0 && <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full px-1 text-[10px] font-bold" style={{ background: "var(--red)" }}>{unresolved}</span>}
            </button>
          </div>
        </header>

        {assets.error && !assets.data && (
          <Card><p className="text-sm" style={{ color: "var(--amber)" }}>Can’t reach the API at <code>{API_BASE}</code> ({assets.error}). Start the services (see README) and this page will fill in automatically.</p></Card>
        )}

        <div className="mb-4"><KpiRow stats={stats.data} /></div>

        {!asset && !assets.error && <Card><Empty>Waiting for the simulator to register assets…</Empty></Card>}
        {asset && (
          <View
            view={view} asset={asset} assets={list} select={setSelectedId} setView={setView}
            twin={twin.data} issues={issues.data ?? []} health={health.data}
          />
        )}
      </div>
    </div>
  );
}

function View({ view, asset, assets, select, setView, twin, issues, health }: {
  view: View; asset: Asset; assets: Asset[]; select: (id: string) => void; setView: (v: View) => void;
  twin: TwinResponse | null; issues: Issue[]; health: ServiceHealth[] | null;
}) {
  const assetIssues = issues.filter((i) => i.asset_id === asset.id);
  const notifications = useApi<AppNotification[]>(view === "alerts" ? "/notifications?limit=50" : null, 4000);
  const picker = <FleetList assets={assets} selectedId={asset.id} onSelect={select} />;

  switch (view) {
    case "overview":
      return (
        <div className="grid gap-4 xl:grid-cols-[250px_minmax(0,1fr)_330px]">
          <div className="order-2 xl:order-1">{picker}</div>
          <div className="order-1 space-y-4 xl:order-2">
            <AssetHeader asset={asset} />
            <div className="grid gap-4 xl:grid-cols-2">
              <TwinPanel asset={asset} twin={twin} />
              <PipelinePanel asset={asset} onTrace={() => setView("workflow")} />
            </div>
            <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
              <TelemetryPanel asset={asset} />
              <RagPanel asset={asset} issues={issues} />
            </div>
            <div className="grid gap-4 xl:grid-cols-[0.7fr_1fr_1.3fr]">
              <McpPanel />
              <ActivityPanel />
              <ArchitecturePanel health={health} />
            </div>
          </div>
          <div className="order-3"><ChatPanel key={asset.id} asset={asset} /></div>
        </div>
      );
    case "fleet":
      return (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          {picker}
          <div className="space-y-4">
            <AssetHeader asset={asset} />
            <Card title="All assets">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead style={{ color: "var(--muted)" }}><tr>{["Asset", "Type", "Status", "Risk", "Health", "Last seen"].map((h) => <th key={h} className="pb-2 pr-3 font-medium">{h}</th>)}</tr></thead>
                  <tbody>
                    {assets.map((a) => (
                      <tr key={a.id} className="cursor-pointer border-t" style={{ borderColor: "var(--line)" }} onClick={() => select(a.id)}>
                        <td className="py-2 pr-3 font-medium">{a.id}</td><td className="pr-3">{a.vehicle_type}</td><td className="pr-3">{a.status}</td>
                        <td className="pr-3">{a.risk_score} ({a.risk_score_numeric.toFixed(0)})</td>
                        <td className="pr-3" style={{ color: healthColor(healthOf(a)) }}>{healthOf(a)}%</td><td>{ago(a.last_seen)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </div>
      );
    case "telemetry":
      return (<div className="grid gap-4 lg:grid-cols-[320px_1fr]">{picker}<div className="space-y-4"><AssetHeader asset={asset} /><TelemetryPanel asset={asset} height={360} /></div></div>);
    case "twin":
      return (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          {picker}
          <div className="space-y-4">
            <AssetHeader asset={asset} />
            <TwinPanel asset={asset} twin={twin} />
            <Card title="Failure prediction">
              <p className="text-sm" style={{ color: "var(--muted)" }}>{twin?.prediction.explanation ?? "Computing…"}</p>
              {twin && <p className="mt-2 text-xs" style={{ color: "var(--faint)" }}>Risk {twin.prediction.risk_score} ({twin.prediction.risk_score_numeric.toFixed(0)}/100){twin.prediction.predicted_failure_horizon_days != null && ` · ~${twin.prediction.predicted_failure_horizon_days.toFixed(0)} days to threshold`}</p>}
            </Card>
            <Card title={`Twin findings (${twin?.state.findings.length ?? 0})`}>
              {twin?.state.findings.length ? (
                <ul className="space-y-2 text-xs">{twin.state.findings.map((f, i) => (<li key={i}><Pill color={f.severity === "high" ? "var(--red)" : f.severity === "medium" ? "var(--amber)" : "var(--green)"}>{f.severity}</Pill> <b>{humanize(f.type)}</b> — <span style={{ color: "var(--muted)" }}>{f.message}</span></li>))}</ul>
              ) : <Empty>No findings: all monitored values are within limits.</Empty>}
            </Card>
          </div>
        </div>
      );
    case "diagnostics":
      return (<div className="grid gap-4 lg:grid-cols-[320px_1fr]">{picker}<div className="space-y-4"><PipelinePanel asset={asset} /><Card title={`Diagnostic issues · ${asset.id}`}><IssuesList issues={assetIssues} /></Card><RagPanel asset={asset} issues={issues} /></div></div>);
    case "workflow":
      return (<div className="grid gap-4 lg:grid-cols-[320px_1fr]">{picker}<div className="space-y-4"><PipelinePanel asset={asset} /><ActivityPanel assetId={asset.id} take={40} title={`Agent trace · ${asset.id}`} /></div></div>);
    case "mcp":
      return <McpPanel full />;
    case "kb":
      return <KnowledgeView vehicleType={asset.vehicle_type} />;
    case "alerts":
      return (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Open issues (fleet)"><IssuesList issues={issues.filter((i) => i.state !== "RESOLVED")} /></Card>
          <Card title="Notifications"><NotificationsList items={notifications.data ?? []} /></Card>
        </div>
      );
    case "healing":
      return (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          {picker}
          <div className="space-y-4"><FaultControl asset={asset} /><Card title={`Self-heal history · ${asset.id}`}><IssuesList issues={assetIssues} showHeal /></Card></div>
        </div>
      );
    case "system":
      return (<div className="grid gap-4 lg:grid-cols-2"><ArchitecturePanel health={health} /><Card title="Services"><SystemHealthCard health={health} /></Card></div>);
    case "settings":
      return (
        <Card title="Settings (read-only)">
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
            <dt style={{ color: "var(--muted)" }}>API base URL</dt><dd className="font-mono">{API_BASE}</dd>
            <dt style={{ color: "var(--muted)" }}>Data</dt><dd>Replay of data/processed (OBD-II diesel PIDs + NASA Li-ion aging)</dd>
            <dt style={{ color: "var(--muted)" }}>LLM</dt><dd>Cohere (COHERE_API_KEY / COHERE_MODEL in .env)</dd>
            <dt style={{ color: "var(--muted)" }}>Store</dt><dd>Local SQLite (data/diagnostics.db)</dd>
          </dl>
        </Card>
      );
  }
}

function KnowledgeView({ vehicleType }: { vehicleType: "EV" | "ICE" }) {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const { data, error } = useApi<KbMatch[]>(submitted ? `/kb/search?q=${encodeURIComponent(submitted)}&top_k=5` : null, 0);
  return (
    <Card title="Knowledge Base (RAG)">
      <form onSubmit={(e) => { e.preventDefault(); setSubmitted(q.trim()); }} className="mb-4 flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search repair knowledge" placeholder={vehicleType === "EV" ? "e.g. battery capacity fade" : "e.g. P0403 EGR circuit"}
          className="flex-1 rounded-md border px-3 py-2 text-sm outline-none" style={{ background: "var(--panel-2)", borderColor: "var(--line)", color: "var(--text)" }} />
        <button className="rounded-md px-4 text-sm text-white" style={{ background: "var(--blue)" }}>Search</button>
      </form>
      {error && <Empty>Search failed ({error}).</Empty>}
      <ul className="space-y-3">
        {data?.map((d) => (
          <li key={d.doc_id} className="rounded-lg border p-3 text-sm" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
            <div className="flex items-center gap-2"><code className="text-xs" style={{ color: "#9ec1ff" }}>{d.doc_id}</code><b>{d.title}</b><Pill color="var(--muted)">{d.retrieval === "cohere-embeddings" ? "similarity" : "keyword"} {d.score.toFixed(2)}</Pill></div>
            <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{d.text}</p>
          </li>
        ))}
        {!submitted && <Empty>Enter a symptom, fault or DTC to search the repair corpus.</Empty>}
      </ul>
    </Card>
  );
}
