import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { Badge } from '../components/Badge';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { SimpleLineChart } from '../components/SimpleLineChart';
import { formatDateTime, formatDuration } from '../utils/formatters';
import { RefreshCw } from 'lucide-react';

export function Reports() {
  const { data: hourlyReports, loading, error, refetch } = usePolling(
    () => api.getHourlyReports(),
    { intervalMs: 5000, enabled: true }
  );

  const downtimeData =
    hourlyReports?.map((r) => ({
      label: new Date(r.time).getHours() + 'h',
      value: r.counters_min.downtime,
    })) || [];

  const producingData =
    hourlyReports?.map((r) => ({
      label: new Date(r.time).getHours() + 'h',
      value: r.counters_min.producing,
    })) || [];

  const completedData =
    hourlyReports?.map((r) => ({
      label: new Date(r.time).getHours() + 'h',
      value: r.completed_count,
    })) || [];

  const latenessData =
    hourlyReports?.map((r) => ({
      label: new Date(r.time).getHours() + 'h',
      value: r.total_lateness_min_est,
    })) || [];

  return (
    <div className="space-y-6">
      <Card title="Hourly Reports">
        <div className="mb-4">
          <Button
            size="sm"
            variant="secondary"
            onClick={refetch}
            disabled={loading}
          >
            <RefreshCw className="w-4 h-4 mr-1 inline" />
            Refresh
          </Button>
        </div>

        {loading && !hourlyReports ? (
          <LoadingSpinner size="lg" />
        ) : error ? (
          <ErrorMessage error={error} onRetry={refetch} />
        ) : hourlyReports && hourlyReports.length > 0 ? (
          <>
            <div className="overflow-x-auto mb-6">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">Time</th>
                    <th className="px-3 py-2 text-left">Running</th>
                    <th className="px-3 py-2 text-left">Down</th>
                    <th className="px-3 py-2 text-left">Queue</th>
                    <th className="px-3 py-2 text-left">Completed</th>
                    <th className="px-3 py-2 text-left">Lateness</th>
                    <th className="px-3 py-2 text-left">Downtime</th>
                    <th className="px-3 py-2 text-left">Producing</th>
                    <th className="px-3 py-2 text-left">Idle</th>
                    <th className="px-3 py-2 text-left">Stopped</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {hourlyReports.map((report, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 whitespace-nowrap font-medium">
                        {formatDateTime(report.time)}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={report.is_running ? 'success' : 'error'}>
                          {report.is_running ? 'YES' : 'NO'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={report.is_down ? 'error' : 'success'}>
                          {report.is_down ? 'YES' : 'NO'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">{report.queue_size}</td>
                      <td className="px-3 py-2 font-semibold">
                        {report.completed_count}
                      </td>
                      <td className="px-3 py-2">
                        {formatDuration(report.total_lateness_min_est)}
                      </td>
                      <td className="px-3 py-2 text-red-700">
                        {formatDuration(report.counters_min.downtime)}
                      </td>
                      <td className="px-3 py-2 text-green-700">
                        {formatDuration(report.counters_min.producing)}
                      </td>
                      <td className="px-3 py-2 text-yellow-700">
                        {formatDuration(report.counters_min.idle)}
                      </td>
                      <td className="px-3 py-2 text-gray-700">
                        {formatDuration(report.counters_min.stopped)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <SimpleLineChart
                data={downtimeData}
                title="Downtime (minutes)"
                color="#dc2626"
                valueFormatter={(v) => `${v.toFixed(0)}min`}
              />
              <SimpleLineChart
                data={producingData}
                title="Producing Time (minutes)"
                color="#16a34a"
                valueFormatter={(v) => `${v.toFixed(0)}min`}
              />
              <SimpleLineChart
                data={completedData}
                title="Completed Jobs"
                color="#2563eb"
                valueFormatter={(v) => v.toFixed(0)}
              />
              <SimpleLineChart
                data={latenessData}
                title="Total Lateness (minutes)"
                color="#ea580c"
                valueFormatter={(v) => `${v.toFixed(0)}min`}
              />
            </div>
          </>
        ) : (
          <div className="text-center text-gray-500 py-8">
            No reports available yet
          </div>
        )}
      </Card>
    </div>
  );
}
