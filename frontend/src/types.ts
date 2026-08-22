export type IncidentType =
  | "memory_leak"
  | "bad_deploy"
  | "dependency_timeout"
  | "traffic_spike"
  | "config_drift";

export type RiskLevel = "low" | "medium" | "high";

export type ActionType =
  | "rollback"
  | "restart_service"
  | "scale_up"
  | "toggle_config_flag";

export type ApprovalStatus = "approved" | "rejected" | null;

export interface FixProposal {
  action_type: ActionType;
  target: string;
  params: Record<string, any>;
}

export interface Event {
  timestamp: string;
  source_agent: string;
  action: string;
  details: string;
}

export interface IncidentState {
  incident_id: string;
  incident_type?: string;
  created_at?: string;
  symptoms?: string[];
  raw_signals?: Record<string, any>;
  root_cause_hypothesis?: string | null;
  confidence_score?: number | null;
  proposed_fix?: FixProposal | null;
  risk_level?: RiskLevel | null;
  approval_status?: ApprovalStatus;
  approval_notes?: string | null;
  resolution?: string | null;
  event_log?: Event[];
  status?: string; // e.g. "pending", "no_anomaly", "error"
  message?: string;
}
