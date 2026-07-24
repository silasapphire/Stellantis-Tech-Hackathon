"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useSustainability } from "@/lib/hooks";

export function SustainabilityPanel({ assetId }: { assetId: string }) {
  const periods = useSustainability(assetId);

  if (periods.length === 0) {
    return (
      <div className="rounded-xl p-6 text-sm" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
        No sustainability data yet — the sustainability sweep records a comparison period periodically.
      </div>
    );
  }

  const data = periods.map((p) => ({
    period: new Date(p.period_end.seconds * 1000).toLocaleDateString([], { month: "short", day: "numeric" }),
    "Actual CO2 (kg)": Number(p.estimated_co2.toFixed(2)),
    "Baseline CO2 (kg)": Number(p.baseline_co2.toFixed(2)),
  }));

  const latest = periods[periods.length - 1];
  const savingsPct = latest.baseline_co2 > 0 ? ((latest.baseline_co2 - latest.estimated_co2) / latest.baseline_co2) * 100 : 0;

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Emissions: actual vs. no-optimization baseline
        </h3>
        <span className="text-sm font-medium" style={{ color: "var(--status-good-text)" }}>
          {savingsPct > 0 ? `${savingsPct.toFixed(0)}% lower` : "—"}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid stroke="var(--gridline)" vertical={false} />
          <XAxis dataKey="period" tick={{ fill: "var(--text-muted)", fontSize: 11 }} stroke="var(--baseline)" />
          <YAxis tick={{ fill: "var(--text-muted)", fontSize: 11 }} stroke="var(--baseline)" width={44} />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--surface-1)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
              color: "var(--text-primary)",
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
          <Bar dataKey="Actual CO2 (kg)" fill="var(--series-1)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
          <Bar dataKey="Baseline CO2 (kg)" fill="var(--series-2)" radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
