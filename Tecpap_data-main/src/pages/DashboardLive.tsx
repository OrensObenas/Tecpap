import { useState, useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { ToastContainer, useToast } from '../components/Toast';
import { formatDateTime, formatDuration, toDatetimeLocal } from '../utils/formatters';
import { Play, Square, Zap, Activity } from 'lucide-react';
import type { EventNowRequest } from '../types/api';

export function DashboardLive() {
  const { toasts, addToast, removeToast } = useToast();

  const [dayStart, setDayStart] = useState(() => {
    const today = new Date();
    today.setHours(8, 0, 0, 0);
    return toDatetimeLocal(today.toISOString());
  });

  const [dayEnd, setDayEnd] = useState(() => {
    const today = new Date();
    today.setHours(16, 0, 0, 0);
    return toDatetimeLocal(today.toISOString());
  });

  const [compressToSeconds, setCompressToSeconds] = useState(120);
  const [tickSeconds, setTickSeconds] = useState(0.2);

  const [actionLoading, setActionLoading] = useState(false);

  // ✅ Stabilise les fonctions passées au polling
  const fetchRealtime = useCallback(() => api.getRealtimeState(), []);
  const fetchEventLog = useCallback(() => api.getEventLog(12), []);

  const {
    data: realtimeState,
    loading,
    error,
    refetch: refetchRealtime,
  } = usePolling(fetchRealtime, { intervalMs: 1000, enabled: true });

  const isRunning = realtimeState?.runner?.running || false;
  const engine = realtimeState?.engine;

  // ✅ Log moins fréquent + seulement si runner en marche
  const {
    data: eventLog,
    refetch: refetchLog,
  } = usePolling(fetchEventLog, {
    intervalMs: 5000,
    enabled: isRunning,
  });

  const safeExecute = useCallback(
    async <T,>(fn: () => Promise<T>) => {
      setActionLoading(true);
      try {
        return await fn();
      } finally {
        setActionLoading(false);
      }
    },
    []
  );

  const handleStart = useCallback(async () => {
    try {
      const result = await safeExecute(() =>
        api.startSimulation({
          day_start: dayStart,
          day_end: dayEnd,
          compress_to_seconds: compressToSeconds,
          tick_seconds: tickSeconds,
        })
      );

      if ((result as any)?.status === 'already_running') {
        addToast('warning', 'Simulation already running');
      } else {
        addToast('success', 'Simulation started');
      }

      // ✅ refresh immédiat
      refetchRealtime();
    } catch (err) {
      addToast('error', 'Failed to start simulation', (err as Error).message);
    }
  }, [
    safeExecute,
    dayStart,
    dayEnd,
    compressToSeconds,
    tickSeconds,
    addToast,
    refetchRealtime,
  ]);

  const handleStop = useCallback(async () => {
    try {
      await safeExecute(() => api.stopSimulation());
      addToast('success', 'Simulation stopped');

      // ✅ refresh immédiat
      refetchRealtime();
    } catch (err) {
      addToast('error', 'Failed to stop simulation', (err as Error).message);
    }
  }, [safeExecute, addToast, refetchRealtime]);

  const sendQuickEvent = useCallback(
    async (event: EventNowRequest) => {
      try {
        const result = await safeExecute(() => api.sendEventNow(event));

        if (result) {
          const msg = (result as any).replanned
            ? `Event sent. Replanned: ${(result as any).replan_reason}`
            : `Event sent (${(result as any).status})`;

          addToast((result as any).status === 'ok' ? 'success' : 'warning', msg);
        }

        // ✅ Au lieu de poller plus vite, on force un refresh juste après action
        refetchRealtime();
        refetchLog();
      } catch (err) {
        addToast('error', 'Failed to send event', (err as Error).message);
      }
    },
    [safeExecute, addToast, refetchRealtime, refetchLog]
  );

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toasts} onClose={removeToast} />

      <Card title="Simulation Control">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Day Start
            </label>
            <input
              type="datetime-local"
              value={dayStart}
              onChange={(e) => setDayStart(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
              disabled={isRunning || actionLoading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Day End
            </label>
            <input
              type="datetime-local"
              value={dayEnd}
              onChange={(e) => setDayEnd(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
              disabled={isRunning || actionLoading}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Compress to (seconds)
            </label>
            <input
              type="number"
              value={compressToSeconds}
              onChange={(e) => setCompressToSeconds(Number(e.target.value))}
              className="w-full border rounded px-3 py-2 text-sm"
              disabled={isRunning || actionLoading}
              min={1}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tick (seconds)
            </label>
            <input
              type="number"
              step="0.1"
              value={tickSeconds}
              onChange={(e) => setTickSeconds(Number(e.target.value))}
              className="w-full border rounded px-3 py-2 text-sm"
              disabled={isRunning || actionLoading}
              min={0.05}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={handleStart}
            disabled={isRunning || actionLoading}
            loading={actionLoading}
            variant="success"
          >
            <Play className="w-4 h-4 mr-1 inline" />
            Start
          </Button>

          <Button
            onClick={handleStop}
            disabled={!isRunning || actionLoading}
            variant="danger"
          >
            <Square className="w-4 h-4 mr-1 inline" />
            Stop
          </Button>
        </div>
      </Card>

      {loading && !realtimeState ? (
        <Card>
          <LoadingSpinner size="lg" />
        </Card>
      ) : error ? (
        <Card>
          <ErrorMessage error={error} onRetry={refetchRealtime} />
        </Card>
      ) : (
        <>
          <Card title="Live State">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <div className="text-sm text-gray-600 mb-1">Simulated Time</div>
                <div className="text-2xl font-bold text-blue-600">
                  {engine?.now ? formatDateTime(engine.now) : 'N/A'}
                </div>
              </div>

              <div>
                <div className="text-sm text-gray-600 mb-1">Runner Status</div>
                <div>
                  <Badge variant={isRunning ? 'success' : 'default'}>
                    {isRunning ? 'RUNNING' : 'PAUSED'}
                  </Badge>
                </div>
              </div>

              <div>
                <div className="text-sm text-gray-600 mb-1">Next Report</div>
                <div className="text-sm font-medium">
                  {realtimeState?.runner?.next_report_time
                    ? formatDateTime(realtimeState.runner.next_report_time)
                    : 'N/A'}
                </div>
              </div>
            </div>

            <div className="border-t pt-4 mt-4">
              <h4 className="font-semibold mb-3 flex items-center">
                <Activity className="w-4 h-4 mr-2" />
                Machine Status
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-xs text-gray-600">Running</div>
                  <Badge variant={engine?.is_running ? 'success' : 'error'}>
                    {engine?.is_running ? 'YES' : 'NO'}
                  </Badge>
                </div>

                <div>
                  <div className="text-xs text-gray-600">Down</div>
                  <Badge variant={engine?.is_down ? 'error' : 'success'}>
                    {engine?.is_down ? 'YES' : 'NO'}
                  </Badge>
                </div>

                <div>
                  <div className="text-xs text-gray-600">Speed Factor</div>
                  <div className="font-bold">{engine?.speed_factor ?? 1.0}</div>
                </div>

                <div>
                  <div className="text-xs text-gray-600">Current Format</div>
                  <div className="font-medium">{engine?.current_format || 'None'}</div>
                </div>
              </div>
            </div>

            {engine?.current_job && (
              <div className="border-t pt-4 mt-4">
                <h4 className="font-semibold mb-3">Current Job</h4>
                <div className="bg-gray-50 rounded p-3">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <div className="text-gray-600">OF ID</div>
                      <div className="font-bold">{engine.current_job.of_id}</div>
                    </div>
                    <div>
                      <div className="text-gray-600">Format</div>
                      <div className="font-medium">{engine.current_job.format}</div>
                    </div>
                    <div>
                      <div className="text-gray-600">Due Date</div>
                      <div className="text-xs">
                        {formatDateTime(engine.current_job.due_date)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600">Priority</div>
                      <Badge variant="info">{engine.current_job.priority}</Badge>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mt-3 text-sm">
                    <div>
                      <div className="text-gray-600">Remaining Setup</div>
                      <div className="font-medium">
                        {engine.remaining_setup_min !== undefined
                          ? formatDuration(engine.remaining_setup_min)
                          : 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600">Remaining Work</div>
                      <div className="font-medium">
                        {engine.remaining_work_nominal_min !== undefined
                          ? formatDuration(engine.remaining_work_nominal_min)
                          : 'N/A'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="border-t pt-4 mt-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-600">Queue Size</div>
                  <div className="text-xl font-bold">{engine?.queue_size ?? 0}</div>
                </div>
                <div>
                  <div className="text-gray-600">Pool Remaining</div>
                  <div className="text-xl font-bold">{engine?.pool_remaining ?? 0}</div>
                </div>
              </div>
            </div>

            {engine?.kpi && (
              <div className="border-t pt-4 mt-4">
                <h4 className="font-semibold mb-3">KPIs</h4>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="bg-red-50 rounded p-3">
                    <div className="text-xs text-gray-600">Downtime</div>
                    <div className="text-lg font-bold text-red-700">
                      {formatDuration(engine.kpi.downtime_min)}
                    </div>
                  </div>
                  <div className="bg-green-50 rounded p-3">
                    <div className="text-xs text-gray-600">Producing</div>
                    <div className="text-lg font-bold text-green-700">
                      {formatDuration(engine.kpi.producing_min)}
                    </div>
                  </div>
                  <div className="bg-yellow-50 rounded p-3">
                    <div className="text-xs text-gray-600">Idle</div>
                    <div className="text-lg font-bold text-yellow-700">
                      {formatDuration(engine.kpi.idle_min)}
                    </div>
                  </div>
                  <div className="bg-gray-50 rounded p-3">
                    <div className="text-xs text-gray-600">Stopped</div>
                    <div className="text-lg font-bold text-gray-700">
                      {formatDuration(engine.kpi.stopped_min)}
                    </div>
                  </div>
                  <div className="bg-blue-50 rounded p-3">
                    <div className="text-xs text-gray-600">Completed</div>
                    <div className="text-lg font-bold text-blue-700">
                      {engine.kpi.completed_count}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card title="Quick Actions">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <Button
                size="sm"
                variant="danger"
                onClick={() => sendQuickEvent({ type: 'BREAKDOWN_START', value: 'MAJOR' })}
                disabled={!isRunning || actionLoading}
              >
                <Zap className="w-3 h-3 mr-1 inline" />
                Breakdown Start
              </Button>

              <Button
                size="sm"
                variant="success"
                onClick={() => sendQuickEvent({ type: 'BREAKDOWN_END', value: 'MAJOR' })}
                disabled={!isRunning || actionLoading}
              >
                Breakdown End
              </Button>

              <Button
                size="sm"
                onClick={() => sendQuickEvent({ type: 'SPEED_CHANGE', value: '0.8' })}
                disabled={!isRunning || actionLoading}
              >
                Speed 0.8x
              </Button>

              <Button
                size="sm"
                onClick={() => sendQuickEvent({ type: 'SPEED_CHANGE', value: '1.0' })}
                disabled={!isRunning || actionLoading}
              >
                Speed 1.0x
              </Button>

              <Button
                size="sm"
                onClick={() => sendQuickEvent({ type: 'SPEED_CHANGE', value: '1.2' })}
                disabled={!isRunning || actionLoading}
              >
                Speed 1.2x
              </Button>

              <Button
                size="sm"
                variant="secondary"
                onClick={() => sendQuickEvent({ type: 'SHIFT_STOP', value: '' })}
                disabled={!isRunning || actionLoading}
              >
                Shift Stop
              </Button>

              <Button
                size="sm"
                variant="success"
                onClick={() => sendQuickEvent({ type: 'SHIFT_START', value: '' })}
                disabled={!isRunning || actionLoading}
              >
                Shift Start
              </Button>
            </div>
          </Card>

          <Card title="Recent Events">
            {!isRunning ? (
              <div className="text-center text-gray-500 py-8">
                Start the simulation to view live events.
              </div>
            ) : eventLog && eventLog.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">Time</th>
                      <th className="px-3 py-2 text-left">Type</th>
                      <th className="px-3 py-2 text-left">Status</th>
                      <th className="px-3 py-2 text-left">Replanned</th>
                      <th className="px-3 py-2 text-left">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {eventLog.slice(0, 12).map((log, idx) => (
                      <tr
                        key={idx}
                        className={log.status === 'ignored' ? 'bg-yellow-50' : ''}
                      >
                        <td className="px-3 py-2 whitespace-nowrap">
                          {formatDateTime(log.received_at)}
                        </td>
                        <td className="px-3 py-2 font-medium">{log.type}</td>
                        <td className="px-3 py-2">
                          <Badge variant={log.status === 'ok' ? 'success' : 'warning'}>
                            {log.status}
                          </Badge>
                        </td>
                        <td className="px-3 py-2">
                          {log.replanned ? <Badge variant="info">YES</Badge> : 'No'}
                        </td>
                        <td className="px-3 py-2">
                          {log.breakdown_duration_min
                            ? formatDuration(log.breakdown_duration_min)
                            : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">No events yet</div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
