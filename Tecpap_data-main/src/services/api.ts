// src/services/api.ts
import type {
  StartSimulationRequest,
  StartSimulationResponse,
  StopSimulationResponse,
  RealtimeState,
  HourlyReport,
  EventRequest,
  EventNowRequest,
  EventResponse,
  EventLog,
  PlanItem,
  EngineState,
  WorkOrder,
  CreateWorkOrderRequest,
  MachinesHistoryResponse,
  MachinesStateResponse,
} from '../types/api';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export class APIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'APIError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
    throw new APIError(
      `HTTP ${response.status}: ${response.statusText}`,
      response.status,
      data
    );
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }

  // CSV/text endpoints
  return (await response.text()) as unknown as T;
}

async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: HeadersInit = {
    ...(options.headers || {}),
  };

  // Inject JSON header only if we send a body and header not already set
  const hasBody = typeof options.body !== 'undefined';
  if (hasBody && !('Content-Type' in headers)) {
    headers['Content-Type'] = 'application/json';
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);
    return await handleResponse<T>(response);
  } catch (err) {
    if (err instanceof APIError) throw err;
    throw new APIError(err instanceof Error ? err.message : 'Network error');
  }
}

export type RecomputePlanResponse = {
  ok: boolean;
  changed: boolean;
  strategy: string;
  before: string[];
  after: string[];
  total_setup_min_est?: number;
  assignments?: {
    of_id: string;
    machine_id?: string;
    start?: string | null;
    end?: string | null;
  }[];
};

export type UrgentOrderPayload = {
  of_id: string;
  due: string; // ISO
  format: string;
  qty: number;
  nominal_rate: number;
  duration_min: number;
  priority?: number;
};

export function buildUrgentOrderValue(payload: UrgentOrderPayload): string {
  const parts = [
    `of_id=${payload.of_id}`,
    `due=${payload.due}`,
    `format=${payload.format}`,
    `qty=${payload.qty}`,
    `nominal_rate=${payload.nominal_rate}`,
    `duration_min=${payload.duration_min}`,
  ];
  if (payload.priority !== undefined) {
    parts.push(`priority=${payload.priority}`);
  }
  return parts.join(';');
}

export const api = {
  // -----------------------
  // Engine state
  // -----------------------
  async getState(): Promise<EngineState> {
    return fetchAPI<EngineState>('/state');
  },

  // -----------------------
  // Realtime runner
  // -----------------------
  async startSimulation(
    params: StartSimulationRequest
  ): Promise<StartSimulationResponse> {
    return fetchAPI<StartSimulationResponse>('/realtime/start', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async stopSimulation(): Promise<StopSimulationResponse> {
    return fetchAPI<StopSimulationResponse>('/realtime/stop', { method: 'POST' });
  },

  async getRealtimeState(): Promise<RealtimeState> {
    return fetchAPI<RealtimeState>('/realtime/state');
  },

  async getHourlyReports(): Promise<HourlyReport[]> {
    return fetchAPI<HourlyReport[]>('/realtime/hourly');
  },

  // -----------------------
  // Events
  // -----------------------
  async sendEvent(event: EventRequest): Promise<EventResponse> {
    return fetchAPI<EventResponse>('/events', {
      method: 'POST',
      body: JSON.stringify(event),
    });
  },

  async sendEventNow(event: EventNowRequest): Promise<EventResponse> {
    return fetchAPI<EventResponse>('/events/now', {
      method: 'POST',
      body: JSON.stringify(event),
    });
  },

  async getEventLog(limit = 100): Promise<EventLog[]> {
    return fetchAPI<EventLog[]>(`/events/log?limit=${limit}`);
  },

  // -----------------------
  // Work Orders (OF)
  // -----------------------
  async getWorkOrders(limit = 200): Promise<WorkOrder[]> {
    return fetchAPI<WorkOrder[]>(`/work-orders?limit=${limit}`);
  },

  async createWorkOrder(payload: CreateWorkOrderRequest): Promise<WorkOrder> {
    return fetchAPI<WorkOrder>('/work-orders', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // -----------------------
  // Planning
  // -----------------------
  async getPlan(limit = 30): Promise<PlanItem[]> {
    return fetchAPI<PlanItem[]>(`/plan?limit=${limit}`);
  },

  async recomputePlan(strategy?: string): Promise<RecomputePlanResponse> {
    // backend n'accepte que MULTI_MACHINE_TRS
    const selected = (strategy || 'MULTI_MACHINE_TRS').toUpperCase();
    const safeStrategy = selected === 'MULTI_MACHINE_TRS' ? selected : 'MULTI_MACHINE_TRS';
    const qs = `?strategy=${encodeURIComponent(safeStrategy)}`;
    return fetchAPI<RecomputePlanResponse>(`/plan/recompute${qs}`, {
      method: 'POST',
    });
  },

  getPlanExportURL(limit = 200): string {
    return `${API_BASE_URL}/plan/export.csv?limit=${limit}`;
  },

  // -----------------------
  // Machines
  // -----------------------
  async getMachineHistory(): Promise<MachinesHistoryResponse> {
    return fetchAPI<MachinesHistoryResponse>('/machines/history');
  },

  async getMachinesState(): Promise<MachinesStateResponse> {
    return fetchAPI<MachinesStateResponse>('/machines/state');
  },
};
