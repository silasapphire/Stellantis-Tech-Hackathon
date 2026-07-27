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
  created_at: { seconds: number; nanoseconds: number } | null;
  last_seen: { seconds: number; nanoseconds: number } | null;
}

export interface TelemetryReading {
  asset_id: string;
  timestamp: string;
  soc?: number | null;
  soh?: number | null;
  pack_voltage?: number | null;
  cell_temp_spread?: number | null;
  motor_temp?: number | null;
  inverter_temp?: number | null;
  charge_rate?: number | null;
  charge_cycles?: number | null;
  rpm?: number | null;
  oil_pressure?: number | null;
  oil_temp?: number | null;
  vibration_index?: number | null;
  fuel_rate?: number | null;
  air_fuel_ratio_proxy?: number | null;
  misfire_count?: number | null;
  coolant_temp?: number | null;
}

export type IssueState = "NEW" | "OPEN" | "MONITORING" | "RESOLVED" | "ESCALATED";
export type Severity = "low" | "medium" | "high";

export interface IssueHistoryEntry {
  state: IssueState;
  timestamp: { seconds: number; nanoseconds: number } | string;
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
  detected_at: { seconds: number; nanoseconds: number };
  resolved_at: { seconds: number; nanoseconds: number } | null;
  explanation: string;
  recommendation: string;
  self_heal_action: string | null;
  self_heal_attempts: number;
  history: IssueHistoryEntry[];
}

export type NotificationType = "alert" | "resolved" | "self_heal" | "escalation" | "prediction";

export interface Notification {
  id: string;
  asset_id: string;
  issue_id: string;
  message: string;
  type: NotificationType;
  created_at: { seconds: number; nanoseconds: number };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  tool_calls: { tool: string; arguments: Record<string, unknown> }[] | null;
  timestamp: { seconds: number; nanoseconds: number };
}

export type AgentName = "diagnostic" | "predictive" | "recommend" | "self_healing" | "sustainability" | "conversational";

export interface AgentActivityEvent {
  id: string;
  asset_id: string;
  agent: AgentName;
  tool: string;
  args: Record<string, unknown>;
  summary: string;
  timestamp: { seconds: number; nanoseconds: number };
}

export interface SustainabilityPeriod {
  id: string;
  period_start: { seconds: number; nanoseconds: number };
  period_end: { seconds: number; nanoseconds: number };
  energy_or_fuel_used: number;
  estimated_co2: number;
  baseline_co2: number;
}
