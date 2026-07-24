"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TelemetryReading } from "@/lib/types";

export interface SeriesSpec {
  key: keyof TelemetryReading;
  label: string;
  color: string;
}

// One axis per chart, by design: never mix metrics of different units/scales
// (e.g. percentage vs. degrees) on a single chart - split into another chart instead.
export function MetricLineChart({
  title,
  unit,
  data,
  series,
}: {
  title: string;
  unit: string;
  data: TelemetryReading[];
  series: SeriesSpec[];
}) {
  const chartData = data.map((reading) => ({
    ...reading,
    time: new Date(reading.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  }));

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          {title}
        </h3>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {unit}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid stroke="var(--gridline)" vertical={false} />
          <XAxis
            dataKey="time"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            stroke="var(--baseline)"
            minTickGap={32}
          />
          <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} stroke="var(--baseline)" width={44} />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--text-primary)",
            }}
            labelStyle={{ color: "var(--text-secondary)" }}
          />
          {series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />}
          {series.map((s) => (
            <Line
              key={String(s.key)}
              type="monotone"
              dataKey={s.key as string}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
