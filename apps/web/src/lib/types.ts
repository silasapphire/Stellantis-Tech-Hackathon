export type VehicleType = "EV" | "ICE";
export type AssetStatus = "healthy" | "warning" | "critical";
export type RiskLevel = "low" | "medium" | "high";

export interface Asset {
  id: string;
  name: string;
  vehicle_type: VehicleType;
  status: AssetStatus;
  risk_score: RiskLevel;
  risk_score_numeric: number;
  created_at: string;
  last_seen: string | null;
  latest?: TelemetryReading | null;
}

export interface TelemetryReading {
  asset_id: string;
  timestamp: string;
  // EV (NASA Li-ion cell data)
  soc?: number | null;
  soh?: number | null;
  capacity_ah?: number | null;
  cell_voltage?: number | null;
  current?: number | null;
  battery_temp?: number | null;
  ambient_temp?: number | null;
  charge_cycles?: number | null;
  phase?: string | null;
  // ICE (OBD-II PIDs, SI units)
  load_pct?: number | null;
  coolant_temp?: number | null;
  map_kpa?: number | null;
  rpm?: number | null;
  speed_kph?: number | null;
  intake_air_temp?: number | null;
  maf?: number | null;
  fuel_rail_pressure_mpa?: number | null;
  baro_kpa?: number | null;
  control_module_voltage?: number | null;
  ambient_air_temp?: number | null;
  drive_mode?: number | null;
  dtc_codes?: string[] | null;
  dtc_count?: number | null;
}

export type IssueState = "NEW" | "OPEN" | "MONITORING" | "RESOLVED" | "ESCALATED";
export type Severity = "low" | "medium" | "high";

export interface IssueHistoryEntry {
  state: IssueState;
  timestamp: string;
  note: string;
  agent: string;
}

export interface Issue {
  id: string;
  asset_id: string;
  type: string;
  state: IssueState;
  severity: Severity;
  confidence: number;
  detected_at: string;
  resolved_at: string | null;
  explanation: string;
  recommendation: string;
  self_heal_action: string | null;
  self_heal_attempts: number;
  history: IssueHistoryEntry[];
}

export interface AppNotification {
  id: string;
  asset_id: string;
  issue_id: string;
  message: string;
  type: "alert" | "resolved" | "self_heal" | "escalation" | "prediction";
  created_at: string;
}

export interface AgentActivityEvent {
  id: string;
  asset_id: string;
  agent: string;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  timestamp: string;
}

export interface Finding {
  type: string;
  severity: Severity;
  field: string;
  value: number;
  threshold: number;
  message: string;
  confidence: number;
}

export interface TwinResponse {
  state: {
    metrics: Record<string, number | null>;
    derived: Record<string, number>;
    findings: Finding[];
    active_dtcs: string[];
  };
  prediction: {
    risk_score: RiskLevel;
    risk_score_numeric: number;
    predicted_failure_horizon_days: number | null;
    explanation: string;
  };
}

export interface PipelineStatus {
  steps: { key: string; label: string; status: "done" | "pending" }[];
  last_event: AgentActivityEvent | null;
  seconds_since_last_event: number | null;
}

export interface Stats {
  fleet: { total: number; ev: number; ice: number };
  active_alerts: { count: number; new_last_hour: number };
  diagnostics_run: { count: number; last_hour: number };
  predictions: { at_risk: number; high_risk: number };
  self_heals: { executed: number; success_pct: number | null };
}

export interface KbMatch {
  doc_id: string;
  fault_type: string;
  vehicle_type: string;
  title: string;
  text: string;
  score: number;
  retrieval: string;
}

export interface McpTool {
  name: string;
  description: string;
  calls: number;
}

export interface ServiceHealth {
  name: string;
  status: "running" | "degraded" | "down";
}
