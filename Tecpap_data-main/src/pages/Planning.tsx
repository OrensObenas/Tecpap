import { useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { formatDateTime, formatDuration } from '../utils/formatters';
import { Download, RefreshCw } from 'lucide-react';

export function Planning() {
  const [limit, setLimit] = useState(30);

  const { data: plan, loading, error, refetch } = usePolling(
    () => api.getPlan(limit),
    { intervalMs: 10000, enabled: false }
  );

  const handleDownloadCSV = () => {
    window.open(api.getPlanExportURL(), '_blank');
  };

  return (
    <div className="space-y-6">
      <Card title="Planning Preview">
        <div className="mb-4 flex gap-4 items-center">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Limit
            </label>
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="border rounded px-3 py-2"
            >
              <option value={30}>30</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
            </select>
          </div>

          <div className="flex gap-2 items-end">
            <Button
              size="sm"
              variant="secondary"
              onClick={refetch}
              disabled={loading}
            >
              <RefreshCw className="w-4 h-4 mr-1 inline" />
              Load Plan
            </Button>

            <Button size="sm" onClick={handleDownloadCSV}>
              <Download className="w-4 h-4 mr-1 inline" />
              Download CSV
            </Button>
          </div>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" />
        ) : error ? (
          <ErrorMessage error={error} onRetry={refetch} />
        ) : plan && plan.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">OF ID</th>
                  <th className="px-3 py-2 text-left">Format</th>
                  <th className="px-3 py-2 text-left">Start</th>
                  <th className="px-3 py-2 text-left">End</th>
                  <th className="px-3 py-2 text-left">Setup</th>
                  <th className="px-3 py-2 text-left">Work (Nominal)</th>
                  <th className="px-3 py-2 text-left">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {plan.map((item, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{item.of_id}</td>
                    <td className="px-3 py-2">{item.format}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDateTime(item.start)}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {formatDateTime(item.end)}
                    </td>
                    <td className="px-3 py-2">{formatDuration(item.setup_min)}</td>
                    <td className="px-3 py-2">
                      {formatDuration(item.work_nominal_min)}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-600">
                      {item.note || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center text-gray-500 py-8">
            Click "Load Plan" to preview the planning
          </div>
        )}
      </Card>
    </div>
  );
}
