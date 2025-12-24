import { useState, useMemo, useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { ToastContainer, useToast } from '../components/Toast';
import { formatDateTime } from '../utils/formatters';
import { Send, RefreshCw, Filter } from 'lucide-react';
import type { EventType } from '../types/api';

export function EventsLogs() {
  const { toasts, addToast, removeToast } = useToast();

  const [eventType, setEventType] = useState<EventType>('BREAKDOWN_START');
  const [eventValue, setEventValue] = useState('');
  const [eventTimestamp, setEventTimestamp] = useState('');
  const [sendMode, setSendMode] = useState<'now' | 'timestamp'>('now');

  const [searchText, setSearchText] = useState('');
  const [filterIgnored, setFilterIgnored] = useState(false);
  const [filterReplanned, setFilterReplanned] = useState(false);
  const [filterBreakdown, setFilterBreakdown] = useState(false);

  const [sendLoading, setSendLoading] = useState(false);

  // ✅ stabilise fetcher (évite relances de polling si rerender)
  const fetchEventLog = useCallback(() => api.getEventLog(200), []);

  // ✅ polling moins agressif qu’avant (2s) + anti-overlap via hook corrigé
  const { data: eventLog, loading, error, refetch } = usePolling(fetchEventLog, {
    intervalMs: 5000,
    enabled: true,
  });

  const handleSendEvent = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (sendMode === 'timestamp' && !eventTimestamp) {
        addToast('error', 'Timestamp is required');
        return;
      }

      setSendLoading(true);
      try {
        let result;

        if (sendMode === 'now') {
          result = await api.sendEventNow({ type: eventType, value: eventValue });
        } else {
          result = await api.sendEvent({
            timestamp: eventTimestamp,
            type: eventType,
            value: eventValue,
          });
        }

        const msg = result.replanned
          ? `Event sent. Replanned: ${result.replan_reason}`
          : `Event sent (${result.status})`;

        addToast(result.status === 'ok' ? 'success' : 'warning', msg);
        setEventValue('');

        // ✅ refresh immédiat après action
        refetch();
      } catch (err) {
        addToast('error', 'Failed to send event', (err as Error).message);
      } finally {
        setSendLoading(false);
      }
    },
    [sendMode, eventTimestamp, addToast, eventType, eventValue, refetch]
  );

  const filteredLogs = useMemo(() => {
    if (!eventLog) return [];

    return eventLog.filter((log) => {
      if (filterIgnored && log.status !== 'ignored') return false;
      if (filterReplanned && !log.replanned) return false;
      if (filterBreakdown && !log.type.includes('BREAKDOWN')) return false;

      if (searchText) {
        const search = searchText.toLowerCase();
        return (
          log.type.toLowerCase().includes(search) ||
          (log.value || '').toLowerCase().includes(search) ||
          (log.reason || '').toLowerCase().includes(search) ||
          (log.replan_reason || '').toLowerCase().includes(search)
        );
      }

      return true;
    });
  }, [eventLog, filterIgnored, filterReplanned, filterBreakdown, searchText]);

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toasts} onClose={removeToast} />

      <Card title="Send Event (Manual)">
        <form onSubmit={handleSendEvent} className="space-y-4">
          <div className="flex gap-4 mb-4">
            <label className="flex items-center">
              <input
                type="radio"
                value="now"
                checked={sendMode === 'now'}
                onChange={(e) => setSendMode(e.target.value as 'now')}
                className="mr-2"
              />
              Send NOW
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                value="timestamp"
                checked={sendMode === 'timestamp'}
                onChange={(e) => setSendMode(e.target.value as 'timestamp')}
                className="mr-2"
              />
              Send with timestamp
            </label>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Event Type *
              </label>
              <select
                value={eventType}
                onChange={(e) => setEventType(e.target.value as EventType)}
                className="w-full border rounded px-3 py-2"
                required
              >
                <option value="BREAKDOWN_START">BREAKDOWN_START</option>
                <option value="BREAKDOWN_END">BREAKDOWN_END</option>
                <option value="SPEED_CHANGE">SPEED_CHANGE</option>
                <option value="SHIFT_START">SHIFT_START</option>
                <option value="SHIFT_STOP">SHIFT_STOP</option>
                <option value="URGENT_JOB">URGENT_JOB</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Value
              </label>
              <input
                type="text"
                value={eventValue}
                onChange={(e) => setEventValue(e.target.value)}
                placeholder="e.g., MAJOR, 1.2, OF_12345"
                className="w-full border rounded px-3 py-2"
              />
            </div>

            {sendMode === 'timestamp' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Timestamp *
                </label>
                <input
                  type="datetime-local"
                  value={eventTimestamp}
                  onChange={(e) => setEventTimestamp(e.target.value)}
                  className="w-full border rounded px-3 py-2"
                  required
                />
              </div>
            )}
          </div>

          <Button type="submit" loading={sendLoading} disabled={sendLoading}>
            <Send className="w-4 h-4 mr-1 inline" />
            Send Event
          </Button>
        </form>
      </Card>

      <Card title="Event Logs">
        <div className="mb-4 space-y-3">
          <div className="flex gap-2 items-center">
            <Button size="sm" variant="secondary" onClick={refetch} disabled={loading}>
              <RefreshCw className="w-4 h-4 mr-1 inline" />
              Refresh
            </Button>

            <input
              type="text"
              placeholder="Search type, value, reason..."
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              className="flex-1 border rounded px-3 py-2 text-sm"
            />
          </div>

          <div className="flex gap-3 items-center text-sm">
            <Filter className="w-4 h-4 text-gray-500" />
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filterIgnored}
                onChange={(e) => setFilterIgnored(e.target.checked)}
                className="mr-1"
              />
              Show only ignored
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filterReplanned}
                onChange={(e) => setFilterReplanned(e.target.checked)}
                className="mr-1"
              />
              Show only replanned
            </label>
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={filterBreakdown}
                onChange={(e) => setFilterBreakdown(e.target.checked)}
                className="mr-1"
              />
              Show only breakdowns
            </label>
          </div>
        </div>

        {loading && !eventLog ? (
          <LoadingSpinner size="lg" />
        ) : error ? (
          <ErrorMessage error={error} onRetry={refetch} />
        ) : filteredLogs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">Received At</th>
                  <th className="px-3 py-2 text-left">Event Time</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Value</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Late</th>
                  <th className="px-3 py-2 text-left">Replanned</th>
                  <th className="px-3 py-2 text-left">Reason</th>
                  <th className="px-3 py-2 text-left">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredLogs.map((log, idx) => (
                  <tr
                    key={idx}
                    className={log.status === 'ignored' ? 'bg-yellow-50' : 'hover:bg-gray-50'}
                  >
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDateTime(log.received_at)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDateTime(log.event_timestamp)}
                    </td>
                    <td className="px-3 py-2 font-medium">{log.type}</td>
                    <td className="px-3 py-2">{log.value || '-'}</td>
                    <td className="px-3 py-2">
                      <Badge variant={log.status === 'ok' ? 'success' : 'warning'}>
                        {log.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      {log.late_applied ? <Badge variant="warning">YES</Badge> : '-'}
                    </td>
                    <td className="px-3 py-2">
                      {log.replanned ? <Badge variant="info">YES</Badge> : '-'}
                    </td>
                    <td className="px-3 py-2 text-xs max-w-xs truncate">
                      {log.reason || log.replan_reason || '-'}
                    </td>
                    <td className="px-3 py-2">
                      {log.breakdown_duration_min ? `${log.breakdown_duration_min}min` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-500 py-8">
            {searchText || filterIgnored || filterReplanned || filterBreakdown
              ? 'No events match the filters'
              : 'No events yet'}
          </div>
        )}
      </Card>
    </div>
  );
}
