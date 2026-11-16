"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Asset, TelemetryReading } from "@/lib/types";
import { fmtTime } from "@/lib/api";

export interface SeriesSpec { key: keyof TelemetryReading; label: string; unit: string; color: string; digits?: number }

export const EV_SERIES: SeriesSpec[] = [
  { key: "soc", label: "SOC", unit: "%", color: "var(--green)", digits: 0 },
  { key: "soh", label: "SOH", unit: "%", color: "var(--blue)", digits: 1 },
  { key: "battery_temp", label: "Battery Temp", unit: "°C", color: "var(--amber)", digits: 1 },
];
export const ICE_SERIES: SeriesSpec[] = [
  { key: "coolant_temp", label: "Coolant Temp", unit: "°C", color: "var(--amber)", digits: 1 },
  { key: "load_pct", label: "Engine Load", unit: "%", color: "var(--blue)", digits: 0 },
  { key: "speed_kph", label: "Speed", unit: "km/h", color: "var(--teal)", digits: 0 },
  { key: "intake_air_temp", label: "Intake Air", unit: "°C", color: "var(--violet)", digits: 1 },
];
export const seriesFor = (type: Asset["vehicle_type"]) => (type === "EV" ? EV_SERIES : ICE_SERIES);

/** All series share one 0-100+ axis, like the reference dashboard; the legend carries units and live values. */
export function TelemetryChart({ readings, series, height = 190 }: { readings: TelemetryReading[]; series: SeriesSpec[]; height?: number }) {
  const data = readings.map((r) => ({ ...r, time: fmtTime(r.timestamp) }));
  const last = readings[readings.length - 1];
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_170px]">
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey="time" tick={{ fill: "var(--faint)", fontSize: 10 }} stroke="var(--line)" minTickGap={40} />
            <YAxis tick={{ fill: "var(--faint)", fontSize: 10 }} stroke="var(--line)" domain={[0, "auto"]} />
            <Tooltip
              contentStyle={{ background: "var(--panel-2)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--text)" }}
              labelStyle={{ color: "var(--muted)" }}
            />
            {series.map((s) => (
              <Line key={String(s.key)} type="monotone" dataKey={s.key as string} name={`${s.label} (${s.unit})`}
                stroke={s.color} strokeWidth={1.8} dot={false} connectNulls isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-2 self-center text-xs">
        {series.map((s) => {
          const v = last?.[s.key];
          return (
            <li key={String(s.key)} className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2" style={{ color: "var(--muted)" }}>
                <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
                {s.label}
              </span>
              <span className="font-mono" style={{ color: s.color }}>
                {typeof v === "number" ? v.toFixed(s.digits ?? 1) : "—"} {s.unit}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Small schematic: battery cell filled to SOC (EV) or an engine block with a coolant bar (ICE). */
export function TwinGlyph({ type, fill, hot }: { type: Asset["vehicle_type"]; fill: number; hot: boolean }) {
  const accent = hot ? "var(--red)" : "var(--teal)";
  const pct = Math.max(0, Math.min(100, fill));
  if (type === "EV") {
    return (
      <svg viewBox="0 0 220 120" className="h-full w-full" role="img" aria-label="Battery cell state of charge">
        <rect x="20" y="30" width="170" height="64" rx="10" fill="none" stroke="var(--blue)" strokeWidth="2" opacity=".7" />
        <rect x="190" y="52" width="14" height="20" rx="3" fill="var(--blue)" opacity=".7" />
        <rect x="26" y="36" width={(158 * pct) / 100} height="52" rx="6" fill={accent} opacity=".85" />
        <path d="M112 42 L98 66 H110 L104 86 L124 58 H112 Z" fill="var(--bg)" opacity=".7" />
        <text x="105" y="112" textAnchor="middle" fontSize="11" fill="var(--muted)">cell SOC {pct.toFixed(0)}%</text>
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 220 120" className="h-full w-full" role="img" aria-label="Engine coolant temperature">
      <rect x="40" y="38" width="120" height="52" rx="8" fill="none" stroke="var(--blue)" strokeWidth="2" opacity=".7" />
      {[62, 88, 114, 140].map((x) => (<rect key={x} x={x - 9} y="22" width="18" height="16" rx="3" fill="none" stroke="var(--blue)" strokeWidth="2" opacity=".7" />))}
      <rect x="160" y="52" width="30" height="24" rx="4" fill="none" stroke="var(--blue)" strokeWidth="2" opacity=".5" />
      <rect x="46" y="44" width={(108 * pct) / 100} height="40" rx="5" fill={accent} opacity=".8" />
      <text x="105" y="112" textAnchor="middle" fontSize="11" fill="var(--muted)">coolant {pct.toFixed(0)}% of 105°C limit</text>
    </svg>
  );
}
