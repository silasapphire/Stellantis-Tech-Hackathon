"use client";

import { useLatestReading } from "@/lib/hooks";
import type { TelemetryReading, VehicleType } from "@/lib/types";

interface Tile {
  key: keyof TelemetryReading;
  label: string;
  unit: string;
  decimals?: number;
}

const EV_TILES: Tile[] = [
  { key: "soc", label: "State of charge", unit: "%" },
  { key: "soh", label: "State of health", unit: "%" },
  { key: "cell_temp_spread", label: "Cell temp spread", unit: "°C", decimals: 1 },
  { key: "motor_temp", label: "Motor temp", unit: "°C" },
  { key: "inverter_temp", label: "Inverter temp", unit: "°C" },
  { key: "coolant_temp", label: "Coolant temp", unit: "°C" },
];

const ICE_TILES: Tile[] = [
  { key: "rpm", label: "RPM", unit: "" },
  { key: "oil_pressure", label: "Oil pressure", unit: "psi" },
  { key: "oil_temp", label: "Oil temp", unit: "°C" },
  { key: "coolant_temp", label: "Coolant temp", unit: "°C" },
  { key: "vibration_index", label: "Vibration", unit: "idx", decimals: 1 },
  { key: "misfire_count", label: "Misfires", unit: "" },
];

export function LiveReadings({ assetId, vehicleType }: { assetId: string; vehicleType: VehicleType }) {
  const reading = useLatestReading(assetId);
  const tiles = vehicleType === "EV" ? EV_TILES : ICE_TILES;

  return (
    <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          Live telemetry
        </h3>
        {reading && (
          <span className="flex items-center gap-1.5 text-xs" style={{ color: "var(--status-good-text)" }}>
            <span className="h-1.5 w-1.5 animate-pulse rounded-full" style={{ backgroundColor: "var(--status-good)" }} />
            streaming
          </span>
        )}
      </div>

      {!reading ? (
        <p className="text-sm" style={{ color: "var(--text-muted)" }}>
          Waiting for the first reading…
        </p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {tiles.map((tile) => {
            const value = reading[tile.key];
            return (
              <div key={String(tile.key)}>
                <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                  {tile.label}
                </div>
                <div className="text-lg font-semibold tabular-nums" style={{ color: "var(--text-primary)" }}>
                  {typeof value === "number" ? value.toFixed(tile.decimals ?? 0) : "—"}
                  {tile.unit && <span className="ml-0.5 text-xs font-normal" style={{ color: "var(--text-muted)" }}>{tile.unit}</span>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
