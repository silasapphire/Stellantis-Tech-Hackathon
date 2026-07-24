"use client";

import { useTelemetryHistory } from "@/lib/hooks";
import type { VehicleType } from "@/lib/types";
import { MetricLineChart } from "./MetricLineChart";

export function AssetTelemetryCharts({ assetId, vehicleType }: { assetId: string; vehicleType: VehicleType }) {
  const readings = useTelemetryHistory(assetId, 80);

  if (readings.length === 0) {
    return (
      <div className="rounded-xl p-6 text-sm" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)", color: "var(--text-muted)" }}>
        Waiting for telemetry…
      </div>
    );
  }

  if (vehicleType === "EV") {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <MetricLineChart
          title="Battery"
          unit="%"
          data={readings}
          series={[
            { key: "soc", label: "State of charge", color: "var(--series-1)" },
            { key: "soh", label: "State of health", color: "var(--series-3)" },
          ]}
        />
        <MetricLineChart
          title="Temperatures"
          unit="°C"
          data={readings}
          series={[
            { key: "cell_temp_spread", label: "Cell temp spread", color: "var(--series-2)" },
            { key: "motor_temp", label: "Motor", color: "var(--series-1)" },
            { key: "inverter_temp", label: "Inverter", color: "var(--series-4)" },
            { key: "coolant_temp", label: "Coolant", color: "var(--series-3)" },
          ]}
        />
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <MetricLineChart
        title="Oil pressure"
        unit="psi"
        data={readings}
        series={[{ key: "oil_pressure", label: "Oil pressure", color: "var(--series-1)" }]}
      />
      <MetricLineChart
        title="Temperatures"
        unit="°C"
        data={readings}
        series={[
          { key: "oil_temp", label: "Oil", color: "var(--series-2)" },
          { key: "coolant_temp", label: "Coolant", color: "var(--series-3)" },
        ]}
      />
      <MetricLineChart
        title="Vibration index"
        unit="index"
        data={readings}
        series={[{ key: "vibration_index", label: "Vibration", color: "var(--series-4)" }]}
      />
      <MetricLineChart
        title="Misfires"
        unit="count"
        data={readings}
        series={[{ key: "misfire_count", label: "Misfire count", color: "var(--status-critical)" }]}
      />
    </div>
  );
}
