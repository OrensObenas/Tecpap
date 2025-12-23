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
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

class APIError extends Error {
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

  const contentType = response.headers.get('content-type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }

  return response.text() as T;
}

async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const defaultHeaders: HeadersInit = {
    'Content-Type': 'application/json',
  };

  const config: RequestInit = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const response = await fetch(url, config);
    return handleResponse<T>(response);
  } catch (error) {
    if (error instanceof APIError) {
      throw error;
    }
    throw new APIError(
      error instanceof Error ? error.message : 'Network error'
    );
  }
}

export const api = {
  async getState(): Promise<EngineState> {
    return fetchAPI<EngineState>('/state');
  },

  async startSimulation(
    params: StartSimulationRequest
  ): Promise<StartSimulationResponse> {
    return fetchAPI<StartSimulationResponse>('/realtime/start', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  },

  async stopSimulation(): Promise<StopSimulationResponse> {
    return fetchAPI<StopSimulationResponse>('/realtime/stop', {
      method: 'POST',
    });
  },

  async getRealtimeState(): Promise<RealtimeState> {
    return fetchAPI<RealtimeState>('/realtime/state');
  },

  async getHourlyReports(): Promise<HourlyReport[]> {
    return fetchAPI<HourlyReport[]>('/realtime/hourly');
  },

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

  async getPlan(limit = 30): Promise<PlanItem[]> {
    return fetchAPI<PlanItem[]>(`/plan?limit=${limit}`);
  },

  getPlanExportURL(): string {
    return `${API_BASE_URL}/plan/export.csv`;
  },
};

export { APIError };
