export interface StartSimulationRequest {
  day_start: string;
  day_end: string;
  compress_to_seconds: number;
  tick_seconds: number;
}

export interface StartSimulationResponse {
  status: 'started' | 'already_running';
}

export interface StopSimulationResponse {
  status: 'stopped';
}

export interface RunnerState {
  running: boolean;
  day_start?: string;
  day_end?: string;
  compress_to_seconds?: number;
  tick_seconds?: number;
  next_report_time?: string;
}

export interface CurrentJob {
  of_id: string;
  format: string;
  due_date: string;
  priority: number;
}

export interface BreakdownInfo {
  type?: string;
  started_at?: string;
  duration_min?: number;
}

export interface KPI {
  downtime_min: number;
  producing_min: number;
  idle_min: number;
  stopped_min: number;
  completed_count: number;
}

export interface EngineState {
  now: string;
  is_running: boolean;
  is_down: boolean;
  speed_factor: number;
  current_format?: string;
  current_job?: CurrentJob;
  remaining_setup_min?: number;
  remaining_work_nominal_min?: number;
  queue_size: number;
  pool_remaining: number;
  breakdown?: BreakdownInfo;
  kpi: KPI;
}

export interface RealtimeState {
  runner: RunnerState;
  engine: EngineState;
}

export interface HourlyReport {
  time: string;
  is_running: boolean;
  is_down: boolean;
  queue_size: number;
  completed_count: number;
  total_lateness_min_est: number;
  counters_min: {
    downtime: number;
    stopped: number;
    idle: number;
    producing: number;
  };
}

export interface EventRequest {
  timestamp?: string;
  type: string;
  value: string;
}

export interface EventNowRequest {
  type: string;
  value: string;
}

export interface EventResponse {
  status: 'ok' | 'ignored';
  replanned?: boolean;
  reason?: string;
  replan_reason?: string;
  breakdown_duration_min?: number;
}

export interface EventLog {
  received_at: string;
  event_timestamp: string;
  type: string;
  value: string;
  status: 'ok' | 'ignored';
  reason?: string;
  late_applied?: boolean;
  replanned?: boolean;
  replan_reason?: string;
  breakdown_duration_min?: number;
}

export interface PlanItem {
  of_id: string;
  format: string;
  start: string;
  end: string;
  setup_min: number;
  work_nominal_min: number;
  note?: string;
}

export type EventType =
  | 'BREAKDOWN_START'
  | 'BREAKDOWN_END'
  | 'SPEED_CHANGE'
  | 'SHIFT_START'
  | 'SHIFT_STOP'
  | 'URGENT_JOB';
