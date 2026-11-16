"use client";

import { useMemo, useState } from "react";
import { API_BASE, ago, fmtTime, postJson, useApi } from "@/lib/api";
import type {
  AgentActivityEvent, AppNotification, Asset, Issue, KbMatch, McpTool, PipelineStatus, ServiceHealth, Stats, TwinResponse,
} from "@/lib/types";
import { Card, Dot, Empty, Pill, SEVERITY_COLOR, STATE_COLOR, STATUS_COLOR, humanize } from "./ui";
import { TelemetryChart, TwinGlyph, seriesFor } from "./charts";

// ---------------------------------------------------------------- helpers
export function healthOf(a: Asset): number {
  if (a.vehicle_type === "EV" && typeof a.latest?.soh === "number") return Math.round(a.latest.soh);
  return Math.max(0, Math.round(100 - a.risk_score_numeric));
}
export const healthBasis = (a: Asset) => (a.vehicle_type === "EV" && typeof a.latest?.soh === "number" ? "battery SOH" : "100 − risk score");
export const healthColor = (h: number) => (h >= 85 ? "var(--green)" : h >= 70 ? "var(--amber)" : "var(--red)");
const isIssue = (a: Asset) => a.status !== "healthy";

// ---------------------------------------------------------------- KPI row
export function KpiRow({ stats }: { stats: Stats | null }) {
  const items = [
    { label: "Fleet Assets", value: stats?.fleet.total, sub: stats ? `EV: ${stats.fleet.ev}  |  ICE: ${stats.fleet.ice}` : "", color: "var(--blue)", icon: "🚗" },
    { label: "Active Alerts", value: stats?.active_alerts.count, chip: stats ? `↑ ${stats.active_alerts.new_last_hour} last hr` : "", chipColor: "var(--red)", color: "var(--red)", icon: "📈" },
    { label: "Diagnostics Run", value: stats?.diagnostics_run.count?.toLocaleString(), chip: stats ? `↑ ${stats.diagnostics_run.last_hour} last hr` : "", chipColor: "var(--green)", color: "var(--blue)", icon: "🔧" },
    { label: "Predictions (At Risk)", value: stats?.predictions.at_risk, chip: stats ? `${stats.predictions.high_risk} High Risk` : "", chipColor: "var(--red)", color: "var(--violet)", icon: "◈" },
    { label: "Self-Heals Executed", value: stats?.self_heals.executed, chip: stats?.self_heals.success_pct != null ? `${stats.self_heals.success_pct}% Effective` : "no attempts yet", chipColor: "var(--green)", color: "var(--green)", icon: "🛡" },
    { label: "Repair Docs (RAG)", value: undefined as number | undefined, ragCount: true, color: "var(--blue)", icon: "📄" },
  ];
  const kb = useApi<{ documents: number }>("/kb/stats", 0);
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {items.map((it) => (
        <div key={it.label} className="flex items-center gap-3 rounded-xl border p-3" style={{ background: "var(--panel)", borderColor: "var(--line)" }}>
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-lg" style={{ background: `color-mix(in srgb, ${it.color} 18%, transparent)` }}>{it.icon}</div>
          <div className="min-w-0">
            <div className="truncate text-xs" style={{ color: "var(--muted)" }}>{it.label}</div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-semibold leading-tight">{it.ragCount ? (kb.data?.documents ?? "—") : (it.value ?? "—")}</span>
              {"chip" in it && it.chip && <Pill color={it.chipColor}>{it.chip}</Pill>}
            </div>
            {"sub" in it && it.sub && <div className="text-[11px]" style={{ color: "var(--faint)" }}>{it.sub}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- fleet list
export function FleetList({ assets, selectedId, onSelect }: { assets: Asset[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [onlyIssues, setOnlyIssues] = useState(false);
  const shown = assets.filter((a) => (!onlyIssues || isIssue(a)) && `${a.name} ${a.id}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <Card title="Fleet (Assets)" right={
      <button onClick={() => setOnlyIssues((v) => !v)} className="rounded-md border px-2 py-1 text-xs"
        style={{ borderColor: "var(--line)", color: onlyIssues ? "var(--amber)" : "var(--muted)" }} aria-pressed={onlyIssues}>
        {onlyIssues ? "Issues only" : "All"} ⏷
      </button>}>
      <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search assets…" aria-label="Search assets"
        className="mb-3 w-full rounded-md border px-3 py-1.5 text-sm outline-none" style={{ background: "var(--panel-2)", borderColor: "var(--line)", color: "var(--text)" }} />
      <ul className="space-y-2">
        {shown.map((a) => {
          const h = healthOf(a);
          const sel = a.id === selectedId;
          return (
            <li key={a.id}>
              <button onClick={() => onSelect(a.id)} className="flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition"
                style={{ background: sel ? "color-mix(in srgb, var(--blue) 14%, var(--panel))" : "var(--panel-2)", borderColor: sel ? "var(--violet)" : "var(--line)" }}>
                <span className="text-lg" aria-hidden>{a.vehicle_type === "EV" ? "⚡" : "⛽"}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-[13px] font-semibold">{a.id}</span>
                    <span className="text-sm font-semibold" style={{ color: healthColor(h) }}>{h}%</span>
                  </span>
                  <span className="mt-1 flex items-center gap-1.5">
                    <Pill color={a.vehicle_type === "EV" ? "var(--blue)" : "var(--amber)"}>{a.vehicle_type}</Pill>
                    {isIssue(a) ? <Pill color={a.status === "critical" ? "var(--red)" : "var(--amber)"}>⚠ Issue</Pill> : <Pill color="var(--green)">+ Healthy</Pill>}
                  </span>
                  <span className="mt-1 block truncate text-[11px]" style={{ color: "var(--faint)" }}>{a.name.split("·")[1]?.trim() ?? a.name}</span>
                </span>
              </button>
            </li>
          );
        })}
        {shown.length === 0 && <Empty>No assets match.</Empty>}
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------- asset header
export function AssetHeader({ asset }: { asset: Asset }) {
  const h = healthOf(asset);
  const l = asset.latest;
  const third = asset.vehicle_type === "EV"
    ? ["Cycles", `${l?.charge_cycles ?? "—"} discharge cycles`]
    : ["Active DTCs", l?.dtc_codes?.length ? l.dtc_codes.join(", ") : "None"];
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-5">
        <div className="grid h-20 w-32 place-items-center rounded-lg text-5xl" style={{ background: "var(--panel-2)" }} aria-hidden>{asset.vehicle_type === "EV" ? "🔋" : "🛢️"}</div>
        <div className="min-w-[160px] flex-1">
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold">{asset.id}</h2>
            <Pill color={asset.vehicle_type === "EV" ? "var(--blue)" : "var(--amber)"}>{asset.vehicle_type}</Pill>
          </div>
          <p className="text-sm" style={{ color: "var(--muted)" }}>{asset.name.split("·")[1]?.trim() ?? asset.name}</p>
          <p className="text-xs" style={{ color: "var(--faint)" }}>
            {asset.vehicle_type === "EV" ? "NASA Li-ion cell (aging dataset)" : "Diesel OBD-II dataset"}
          </p>
        </div>
        <div className="w-44 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }} title={`Health basis: ${healthBasis(asset)}`}>
          <div className="text-xs" style={{ color: "var(--muted)" }}>Health Score</div>
          <div className="text-3xl font-semibold" style={{ color: healthColor(h) }}>{h}%</div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full" style={{ background: "var(--line)" }}>
            <div className="h-full rounded-full" style={{ width: `${h}%`, background: healthColor(h) }} />
          </div>
          <div className="mt-1 text-[10px]" style={{ color: "var(--faint)" }}>{healthBasis(asset)}</div>
        </div>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
          <dt style={{ color: "var(--muted)" }}>Status</dt>
          <dd className="font-medium" style={{ color: STATUS_COLOR[asset.status] }}>{asset.status === "healthy" ? "Healthy" : "⚠ Issue Detected"}</dd>
          <dt style={{ color: "var(--muted)" }}>Last Reading</dt><dd>{ago(asset.last_seen)}</dd>
          <dt style={{ color: "var(--muted)" }}>{third[0]}</dt><dd>{third[1]}</dd>
        </dl>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- digital twin
const EV_ROWS: [string, string, string, number][] = [
  ["Battery (SOC)", "soc", "%", 0], ["State of Health", "soh", "%", 1], ["Capacity", "capacity_ah", "Ah", 2],
  ["Cell Voltage", "cell_voltage", "V", 3], ["Battery Temp", "battery_temp", "°C", 1], ["Current", "current", "A", 2],
  ["Ambient Temp", "ambient_temp", "°C", 0],
];
const ICE_ROWS: [string, string, string, number][] = [
  ["Coolant (ECT)", "coolant_temp", "°C", 1], ["Engine RPM", "rpm", "rpm", 0], ["Engine Load", "load_pct", "%", 0],
  ["Vehicle Speed", "speed_kph", "km/h", 0], ["Module Voltage", "control_module_voltage", "V", 2], ["Intake MAP", "map_kpa", "kPa", 0],
  ["Fuel Rail", "fuel_rail_pressure_mpa", "MPa", 1], ["Intake Air", "intake_air_temp", "°C", 1],
];

export function TwinPanel({ asset, twin }: { asset: Asset; twin: TwinResponse | null }) {
  const rows = asset.vehicle_type === "EV" ? EV_ROWS : ICE_ROWS;
  const flagged = new Set(twin?.state.findings.map((f) => f.field));
  const m = twin?.state.metrics ?? {};
  const fill = asset.vehicle_type === "EV" ? (m.soc ?? 0) : Math.min(100, ((m.coolant_temp ?? 0) / 105) * 100);
  const risk = twin?.prediction.risk_score_numeric ?? asset.risk_score_numeric;
  return (
    <Card title="Digital Twin" icon={<span style={{ color: "var(--blue)" }}>✦</span>} right={<Pill color="var(--green)"><Dot color="var(--green)" /> Live Twin</Pill>}>
      <div className="grid grid-cols-1 items-center gap-3 sm:grid-cols-[1fr_190px]">
        <div className="h-32"><TwinGlyph type={asset.vehicle_type} fill={fill} hot={flagged.has("battery_temp") || flagged.has("coolant_temp")} /></div>
        <ul className="space-y-1.5 text-xs">
          {rows.map(([label, key, unit, digits]) => {
            const v = m[key];
            const bad = flagged.has(key);
            return (
              <li key={key} className="flex items-center justify-between rounded-md px-2 py-1" style={{ background: "var(--panel-2)" }}>
                <span style={{ color: "var(--muted)" }}>{label}</span>
                <span className="font-mono" style={{ color: bad ? "var(--red)" : "var(--text)" }}>{typeof v === "number" ? v.toFixed(digits) : "—"} {unit}</span>
              </li>
            );
          })}
          {asset.vehicle_type === "ICE" && (
            <li className="flex items-center justify-between rounded-md px-2 py-1" style={{ background: "var(--panel-2)" }}>
              <span style={{ color: "var(--muted)" }}>Active DTCs</span>
              <span className="font-mono" style={{ color: twin?.state.active_dtcs.length ? "var(--red)" : "var(--green)" }}>{twin?.state.active_dtcs.length ?? 0}</span>
            </li>
          )}
          <li className="flex items-center justify-between rounded-md px-2 py-1" style={{ background: "var(--panel-2)" }}>
            <span style={{ color: "var(--muted)" }}>Health (Twin)</span>
            <span className="font-mono" style={{ color: healthColor(100 - risk) }}>{((100 - risk) / 100).toFixed(2)}</span>
          </li>
        </ul>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- LangGraph pipeline
export function PipelinePanel({ asset, onTrace }: { asset: Asset; onTrace?: () => void }) {
  const { data } = useApi<PipelineStatus>(`/pipeline/${asset.id}`, 3000);
  const recent = data?.seconds_since_last_event != null && data.seconds_since_last_event < 180;
  const steps = data?.steps ?? [];
  const firstPending = steps.findIndex((s) => s.status === "pending");
  const lastEvent = data?.last_event;
  return (
    <Card title="LangGraph Agent Pipeline" icon={<span style={{ color: "var(--violet)" }}>⛓</span>}
      right={<Pill color={recent ? "var(--green)" : "var(--muted)"}><Dot color={recent ? "var(--green)" : "var(--faint)"} /> {recent ? `Running (${asset.id})` : "Idle · next sweep"}</Pill>}>
      <ol className="flex items-center gap-1.5">
        {(steps.length ? steps : [{ key: "d", label: "Diagnose", status: "pending" }, { key: "p", label: "Predict", status: "pending" }, { key: "r", label: "Recommend", status: "pending" }, { key: "s", label: "Self-Heal", status: "pending" }] as PipelineStatus["steps"]).map((s, i, arr) => {
          const active = recent && i === firstPending;
          const color = s.status === "done" ? "var(--green)" : active ? "var(--violet)" : "var(--faint)";
          return (
            <li key={s.key} className="flex flex-1 items-center gap-1.5">
              <div className="flex flex-1 flex-col items-center gap-1 rounded-lg border px-2 py-2 text-center text-xs"
                style={{ borderColor: `color-mix(in srgb, ${color} 55%, transparent)`, background: `color-mix(in srgb, ${color} 10%, transparent)`, color: s.status === "done" || active ? "var(--text)" : "var(--faint)" }}>
                <span className={active ? "spin-slow" : ""} style={{ color }} aria-hidden>{s.status === "done" ? "✓" : active ? "◌" : "○"}</span>
                {s.label}
              </div>
              {i < arr.length - 1 && <span style={{ color: "var(--faint)" }} aria-hidden>→</span>}
            </li>
          );
        })}
      </ol>
      <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-xs" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
        <div className="min-w-0">
          <div className="font-medium" style={{ color: "var(--violet)" }}>
            {lastEvent ? `Last step: ${humanize(lastEvent.agent)}` : "Waiting for the first diagnostic sweep"}
          </div>
          <div className="truncate" style={{ color: "var(--muted)" }}>{lastEvent ? `${lastEvent.tool} → ${lastEvent.summary}` : "The scheduler runs the graph for every asset on an interval."}</div>
        </div>
        {onTrace && <button onClick={onTrace} className="shrink-0 rounded-md border px-2 py-1" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>View Trace ›</button>}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- telemetry
export function TelemetryPanel({ asset, height }: { asset: Asset; height?: number }) {
  const { data } = useApi<import("@/lib/types").TelemetryReading[]>(`/telemetry/${asset.id}/history?limit=80`, 3000);
  const readings = useMemo(() => (data ? [...data].reverse() : []), [data]);
  return (
    <Card title={`Live Telemetry (${asset.id})`} icon={<span style={{ color: "var(--teal)" }}>〰</span>} right={<Pill color="var(--green)"><Dot color="var(--green)" /> Live</Pill>}>
      {readings.length ? <TelemetryChart readings={readings} series={seriesFor(asset.vehicle_type)} height={height} /> : <Empty>Waiting for telemetry…</Empty>}
    </Card>
  );
}

// ---------------------------------------------------------------- RAG
export function RagPanel({ asset, issues, limit = 3 }: { asset: Asset; issues: Issue[]; limit?: number }) {
  const open = issues.find((i) => i.asset_id === asset.id && i.state !== "RESOLVED");
  const query = open ? `${humanize(open.type)} ${open.explanation}`.slice(0, 300) : asset.vehicle_type === "EV" ? "battery maintenance best practices" : "diesel engine maintenance best practices";
  const { data, error } = useApi<KbMatch[]>(`/kb/search?q=${encodeURIComponent(query)}&vehicle_type=${asset.vehicle_type}&top_k=${limit}`, 0);
  return (
    <Card title="RAG – Repair Knowledge" icon={<span style={{ color: "var(--blue)" }}>📖</span>} right={<Pill color="var(--muted)">Top Matches</Pill>}>
      <p className="mb-2 truncate text-[11px]" style={{ color: "var(--faint)" }}>query: {open ? humanize(open.type) : "general maintenance"}</p>
      <ul className="space-y-2">
        {data?.map((d) => (
          <li key={d.doc_id} className="flex items-center gap-2 rounded-lg border px-2 py-2 text-xs" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
            <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "color-mix(in srgb, var(--blue) 25%, transparent)", color: "#9ec1ff" }}>{d.doc_id.replace("R-", "R-")}</span>
            <span className="min-w-0 flex-1 truncate">{d.title}</span>
            <span style={{ color: "var(--muted)" }} title={d.retrieval}>{d.retrieval === "cohere-embeddings" ? "Similarity:" : "Keyword:"} <b style={{ color: "var(--text)" }}>{d.score.toFixed(2)}</b></span>
          </li>
        ))}
        {!data && !error && <Empty>Retrieving…</Empty>}
        {error && <Empty>Knowledge base unavailable ({error}).</Empty>}
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------- MCP tools
export function McpPanel({ full = false }: { full?: boolean }) {
  const { data } = useApi<McpTool[]>("/mcp/tools", 15000);
  const tools = data ?? [];
  const shown = full ? tools : tools.slice(0, 6);
  return (
    <Card title={`MCP Tools (${tools.length})`} icon={<span style={{ color: "var(--blue)" }}>🔌</span>}>
      <ul className={full ? "grid gap-2 md:grid-cols-2" : "flex flex-wrap gap-1.5"}>
        {shown.map((t) =>
          full ? (
            <li key={t.name} className="rounded-lg border p-3 text-xs" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
              <div className="flex items-center justify-between gap-2"><code className="font-mono text-[12px]" style={{ color: "#9ec1ff" }}>{t.name}</code><Pill color={t.calls ? "var(--green)" : "var(--faint)"}>{t.calls} calls</Pill></div>
              <p className="mt-1" style={{ color: "var(--muted)" }}>{t.description}</p>
            </li>
          ) : (
            <li key={t.name} className="rounded-md border px-2 py-1 font-mono text-[11px]" style={{ borderColor: "var(--line)", background: "var(--panel-2)", color: t.calls ? "var(--text)" : "var(--muted)" }}>
              {t.calls > 0 && "+ "}{t.name}
            </li>
          ),
        )}
        {!full && tools.length > 6 && <li className="rounded-md border px-2 py-1 text-[11px]" style={{ borderColor: "var(--line)", color: "var(--muted)" }}>+{tools.length - 6} more</li>}
        {!data && <Empty>Loading tools…</Empty>}
      </ul>
    </Card>
  );
}

// ---------------------------------------------------------------- recent activity
function activityBadge(e: AgentActivityEvent): [string, string] {
  if (e.tool.startsWith("kb_")) return ["RAG", "var(--blue)"];
  if (e.tool === "diagnostics_detect_anomaly") return ["DIAG", "var(--red)"];
  if (e.tool.startsWith("twin_")) return ["PREDICT", "var(--amber)"];
  if (e.tool.startsWith("actions_")) return ["HEAL", "var(--green)"];
  if (e.tool.startsWith("telemetry_")) return ["TELEMETRY", "var(--teal)"];
  return ["AGENT", "var(--violet)"];
}

export function ActivityPanel({ assetId, take = 6, title = "Recent Activity (System)" }: { assetId?: string; take?: number; title?: string }) {
  const { data } = useApi<AgentActivityEvent[]>(`/activity?limit=${take}${assetId ? `&asset_id=${assetId}` : ""}`, 3000);
  return (
    <Card title={title} icon={<span style={{ color: "var(--violet)" }}>◈</span>}>
      {data?.length ? (
        <ul className="space-y-1.5 text-xs">
          {data.map((e) => {
            const [label, color] = activityBadge(e);
            return (
              <li key={e.id} className="flex items-start gap-2">
                <span className="w-14 shrink-0 font-mono" style={{ color: "var(--faint)" }}>{fmtTime(e.timestamp)}</span>
                <Pill color={color} className="w-[72px] shrink-0 justify-center">{label}</Pill>
                <span style={{ color: "var(--muted)" }}><b style={{ color: "var(--text)" }}>{e.asset_id}</b> · {e.summary}</span>
              </li>
            );
          })}
        </ul>
      ) : <Empty>No agent activity yet — the first diagnostic sweep runs shortly after startup (requires COHERE_API_KEY).</Empty>}
    </Card>
  );
}

// ---------------------------------------------------------------- architecture
function ArchBox({ x, y, w = 100, label, sub, c }: { x: number; y: number; w?: number; label: string; sub: string; c: string }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height="40" rx="7" fill={`color-mix(in srgb, ${c} 14%, var(--panel))`} stroke={c} strokeWidth="1.5" />
      <text x={x + w / 2} y={y + 17} textAnchor="middle" fontSize="11.5" fontWeight="600" fill="var(--text)">{label}</text>
      <text x={x + w / 2} y={y + 31} textAnchor="middle" fontSize="8.5" fill="var(--muted)">{sub}</text>
    </g>
  );
}
function ArchArrow({ d }: { d: string }) {
  return <path d={d} stroke="var(--faint)" strokeWidth="1.4" fill="none" markerEnd="url(#arr)" />;
}

export function ArchitecturePanel({ health }: { health: ServiceHealth[] | null }) {
  const color = (name: string) => {
    const s = health?.find((h) => h.name.toLowerCase().startsWith(name))?.status;
    return s === "running" ? "var(--green)" : s === "degraded" ? "var(--amber)" : s === "down" ? "var(--red)" : "var(--faint)";
  };
  return (
    <Card title="System Architecture (Live)" icon={<span style={{ color: "var(--teal)" }}>⌘</span>}>
      <svg viewBox="0 0 330 190" className="w-full" role="img" aria-label="Architecture: simulator to API to store, agents to MCP server to twin service and Cohere">
        <defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="var(--faint)" /></marker></defs>
        <ArchBox x={2} y={6} label="Simulator" sub="real data replay" c={color("simulator")} />
        <ArchBox x={115} y={6} label="FastAPI" sub="+ Scheduler" c={color("fastapi")} />
        <ArchBox x={228} y={6} label="SQLite" sub="document store" c={color("document")} />
        <ArchArrow d="M104 26 H113" /><ArchArrow d="M217 26 H226" />
        <ArchBox x={115} y={78} label="LangGraph" sub="4-step agent graph" c="var(--violet)" />
        <ArchBox x={228} y={78} label="Cohere" sub="LLM + embeddings" c="var(--blue)" />
        <ArchBox x={115} y={148} label="MCP Server" sub="14 tools" c={color("mcp")} />
        <ArchBox x={228} y={148} label="Twin Service" sub="EV / ICE" c={color("twin")} />
        <ArchArrow d="M165 48 V76" /><ArchArrow d="M217 98 H226" /><ArchArrow d="M165 120 V146" /><ArchArrow d="M217 168 H226" />
      </svg>
    </Card>
  );
}

// ---------------------------------------------------------------- system health card (sidebar)
export function SystemHealthCard({ health }: { health: ServiceHealth[] | null }) {
  const down = health?.filter((h) => h.status !== "running").length ?? 0;
  const ok = health && down === 0;
  return (
    <div className="rounded-xl border p-3" style={{ background: "var(--panel)", borderColor: "var(--line)" }}>
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold" style={{ color: ok ? "var(--green)" : "var(--amber)" }}>
        <Dot color={ok ? "var(--green)" : "var(--amber)"} /> {health ? (ok ? "System Healthy" : `${down} service(s) need attention`) : "Checking…"}
      </div>
      <ul className="space-y-1 text-[11px]">
        {health?.map((h) => (
          <li key={h.name} className="flex justify-between"><span style={{ color: "var(--muted)" }}>{h.name}</span>
            <span style={{ color: h.status === "running" ? "var(--green)" : h.status === "degraded" ? "var(--amber)" : "var(--red)" }}>{h.status === "running" ? "Running" : h.status}</span></li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- issues list (diagnostics / alerts / self-healing)
export function IssuesList({ issues, showHeal = false }: { issues: Issue[]; showHeal?: boolean }) {
  if (!issues.length) return <Empty>No issues recorded.</Empty>;
  return (
    <ul className="space-y-3">
      {issues.map((i) => (
        <li key={i.id} className="rounded-lg border p-3 text-sm" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
          <div className="flex flex-wrap items-center gap-2">
            <b>{humanize(i.type)}</b><span className="text-xs" style={{ color: "var(--faint)" }}>{i.asset_id}</span>
            <Pill color={STATE_COLOR[i.state]}>{i.state}</Pill><Pill color={SEVERITY_COLOR[i.severity]}>{i.severity}</Pill>
            <Pill color="var(--muted)">{Math.round(i.confidence * 100)}% confidence</Pill>
            <span className="ml-auto text-xs" style={{ color: "var(--faint)" }}>{ago(i.detected_at)}</span>
          </div>
          {i.explanation && <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{i.explanation}</p>}
          {i.recommendation && <p className="mt-2 rounded-md px-2 py-1.5 text-xs" style={{ background: "color-mix(in srgb, var(--teal) 10%, transparent)", color: "var(--text)" }}><b style={{ color: "var(--teal)" }}>Recommended (RAG): </b>{i.recommendation}</p>}
          {showHeal && (
            <div className="mt-2 text-xs" style={{ color: "var(--muted)" }}>
              Self-heal attempts: <b style={{ color: "var(--text)" }}>{i.self_heal_attempts}</b>{i.self_heal_action && <> · last action <code className="font-mono">{i.self_heal_action}</code></>}
              <ul className="mt-1 space-y-0.5">
                {i.history.filter((h) => h.agent === "self_healing" || h.state === "ESCALATED" || h.state === "RESOLVED").map((h, k) => (
                  <li key={k}>{fmtTime(h.timestamp)} · {h.state} — {h.note}</li>
                ))}
              </ul>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

export function NotificationsList({ items }: { items: AppNotification[] }) {
  if (!items.length) return <Empty>No notifications.</Empty>;
  const color = { alert: "var(--red)", resolved: "var(--green)", self_heal: "var(--blue)", escalation: "var(--red)", prediction: "var(--violet)" } as const;
  return (
    <ul className="space-y-1.5 text-xs">
      {items.map((n) => (
        <li key={n.id} className="flex items-start gap-2"><span className="w-14 shrink-0 font-mono" style={{ color: "var(--faint)" }}>{fmtTime(n.created_at)}</span>
          <Pill color={color[n.type]}>{n.type}</Pill><span style={{ color: "var(--muted)" }}><b style={{ color: "var(--text)" }}>{n.asset_id}</b> · {n.message}</span></li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------- demo fault control (self-healing view)
interface SimPreset { field: string; target_value: number; vehicle_type: string; label: string; unit: string; lo: number; hi: number; hint: string; ramp_seconds: number }
interface SimFault { fault_type: string; field: string; target_value: number; clearing: boolean; progress: number; ramp_ticks: number }
interface SimStatus {
  tick_seconds: number;
  assets: Record<string, SimFault | null>;
  presets: Record<string, SimPreset>;
  autopilot: { enabled: boolean; interval_seconds: number; hold_seconds: number; last_event: string | null };
}

export function FaultControl({ asset }: { asset: Asset }) {
  const { data, error, reload } = useApi<SimStatus>("/simulator/status", 2000);
  const presets = Object.entries(data?.presets ?? {}).filter(([, p]) => p.vehicle_type === asset.vehicle_type);
  const [choice, setChoice] = useState<string | null>(null);
  const [severity, setSeverity] = useState<number | null>(null);
  const [rampSec, setRampSec] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [apInterval, setApInterval] = useState(90);
  const [apHold, setApHold] = useState(120);

  const key = choice && data?.presets[choice]?.vehicle_type === asset.vehicle_type ? choice : presets[0]?.[0];
  const preset = key ? data?.presets[key] : undefined;
  const target = severity ?? preset?.target_value ?? 0;
  const ramp = rampSec ?? preset?.ramp_seconds ?? 30;
  const active = data?.assets[asset.id] ?? null;
  const ap = data?.autopilot;

  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); setMsg(ok); reload(); } catch (e) { setMsg(`Failed: ${e instanceof Error ? e.message : e}`); }
  }
  const btn = "rounded-md border px-3 py-1.5 text-xs transition hover:brightness-125 active:scale-95 disabled:opacity-40 disabled:hover:brightness-100";

  return (
    <Card title="Fault simulation control" right={<Pill color="var(--amber)">overlay on real data</Pill>}>
      <p className="mb-3 text-xs" style={{ color: "var(--muted)" }}>
        Real recorded data is replayed untouched; this overlays a temporary fault on <b style={{ color: "var(--text)" }}>{asset.id}</b> so
        the diagnose → self-heal → resolve loop can be shown. Self-heal can clear an injected fault, never a genuine DTC or battery degradation.
      </p>
      {error && <p className="mb-2 text-xs" style={{ color: "var(--red)" }}>Simulator unreachable ({error}).</p>}

      <div className="mb-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Fault type">
        {presets.map(([k, p]) => (
          <button key={k} role="radio" aria-checked={k === key} onClick={() => { setChoice(k); setSeverity(null); setRampSec(null); }}
            className={btn} style={{ borderColor: k === key ? "var(--blue)" : "var(--line)", background: k === key ? "color-mix(in srgb, var(--blue) 20%, var(--panel-2))" : "var(--panel-2)", color: "var(--text)" }}>
            {p.label}
          </button>
        ))}
      </div>

      {preset && (
        <div className="mb-3 grid gap-4 sm:grid-cols-2">
          <label className="text-xs" style={{ color: "var(--muted)" }}>
            Severity — ramp {preset.field.replace(/_/g, " ")} to <b style={{ color: "var(--text)" }}>{target.toFixed(preset.unit === "V" ? 1 : 0)} {preset.unit}</b>
            <input type="range" className="mt-1 w-full" min={preset.lo} max={preset.hi} step={preset.unit === "V" ? 0.1 : 1} value={target} onChange={(e) => setSeverity(+e.target.value)} />
            <span className="text-[11px]" style={{ color: "var(--faint)" }}>{preset.hint}</span>
          </label>
          <label className="text-xs" style={{ color: "var(--muted)" }}>
            Speed — ramps in over <b style={{ color: "var(--text)" }}>{ramp.toFixed(0)} s</b>
            <input type="range" className="mt-1 w-full" min={6} max={120} step={3} value={ramp} onChange={(e) => setRampSec(+e.target.value)} />
            <span className="text-[11px]" style={{ color: "var(--faint)" }}>Issues appear within ~30 s of crossing a threshold (detection sweep).</span>
          </label>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button disabled={!preset || !!active} className={btn} style={{ borderColor: "var(--red)", background: "color-mix(in srgb, var(--red) 18%, var(--panel-2))", color: "var(--text)" }}
          onClick={() => act(() => postJson(`/assets/${asset.id}/inject-fault`, { fault_type: key, target_value: target, ramp_seconds: ramp }), `Injecting ${preset?.label} on ${asset.id}.`)}>
          ▶ Inject fault
        </button>
        <button disabled={!active || active.clearing} className={btn} style={{ borderColor: "var(--green)", background: "color-mix(in srgb, var(--green) 16%, var(--panel-2))", color: "var(--text)" }}
          onClick={() => act(async () => { await fetch(`${API_BASE}/assets/${asset.id}/fault`, { method: "DELETE" }); }, `Clearing the fault on ${asset.id}; values ramp back to the real data.`)}>
          ■ Clear now
        </button>
        {active ? (
          <span className="text-xs" style={{ color: "var(--muted)" }} role="status">
            Active: <b style={{ color: "var(--text)" }}>{data?.presets[active.fault_type]?.label}</b> — {active.clearing ? "recovering" : "ramping"} {Math.round(active.progress * 100)}%
          </span>
        ) : <span className="text-xs" style={{ color: "var(--faint)" }}>No injected fault on this asset.</span>}
      </div>
      {msg && <p className="mt-2 text-xs" style={{ color: "var(--muted)" }}>{msg}</p>}

      <div className="mt-4 rounded-lg border p-3" style={{ borderColor: "var(--line)", background: "var(--panel-2)" }}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-semibold">Autopilot <span className="font-normal" style={{ color: "var(--faint)" }}>— random fault on a random asset, one at a time, cleared automatically</span></div>
          <button className={btn} aria-pressed={!!ap?.enabled}
            style={{ borderColor: ap?.enabled ? "var(--green)" : "var(--line)", background: ap?.enabled ? "color-mix(in srgb, var(--green) 20%, var(--panel))" : "var(--panel)", color: "var(--text)" }}
            onClick={() => act(() => postJson("/simulator/autopilot", { enabled: !ap?.enabled, interval_seconds: apInterval, hold_seconds: apHold }), ap?.enabled ? "Autopilot stopped." : "Autopilot started.")}>
            {ap?.enabled ? "● ON — click to stop" : "○ OFF — click to start"}
          </button>
        </div>
        <div className="mt-2 grid gap-3 sm:grid-cols-2 text-xs" style={{ color: "var(--muted)" }}>
          <label>New fault every <b style={{ color: "var(--text)" }}>{apInterval}s</b><input type="range" className="w-full" min={30} max={300} step={10} value={apInterval} onChange={(e) => setApInterval(+e.target.value)} /></label>
          <label>Hold for <b style={{ color: "var(--text)" }}>{apHold}s</b> before clearing<input type="range" className="w-full" min={30} max={300} step={10} value={apHold} onChange={(e) => setApHold(+e.target.value)} /></label>
        </div>
        {ap?.last_event && <p className="mt-1 text-[11px]" style={{ color: "var(--faint)" }}>last: {ap.last_event}</p>}
        <p className="mt-1 text-[11px]" style={{ color: "var(--faint)" }}>Interval/hold apply when you start (restart to change). A self-heal can clear the fault before the hold ends.</p>
      </div>
    </Card>
  );
}
