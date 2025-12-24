// src/pages/Planning.tsx
import { useMemo, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { api } from '../services/api';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { formatDateTime, formatDuration } from '../utils/formatters';
import { Download, RefreshCw, Plus, Shuffle } from 'lucide-react';

export function Planning() {
  const [tab, setTab] = useState<'orders' | 'schedule'>('orders');
  const [limit, setLimit] = useState(30);

  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({
    of_id: '',
    format: 'F1',
    due_date: '',
    priority: 5,
    work_nominal_min: 60,
  });

  const [strategy, setStrategy] = useState<'FORMAT_PRIORITY' | 'EDD_SETUP'>(
    'FORMAT_PRIORITY'
  );

  // polling disabled: manual reload only (évite de spammer ton backend)
  const woPoll = usePolling(() => api.getWorkOrders(200), {
    intervalMs: 10_000,
    enabled: false,
  });

  const planPoll = usePolling(() => api.getPlan(limit), {
    intervalMs: 10_000,
    enabled: false,
  });

  const active = tab === 'orders' ? woPoll : planPoll;

  const canSubmit = useMemo(() => {
    return form.of_id.trim().length > 0 && form.format.trim().length > 0;
  }, [form.of_id, form.format]);

  const handleReload = async () => {
    await woPoll.refetch();
    await planPoll.refetch();
  };

  const handleDownloadCSV = () => {
    window.open(api.getPlanExportURL(limit), '_blank');
  };

  const handleAdd = async () => {
    if (!canSubmit) return;

    await api.createWorkOrder({
      of_id: form.of_id.trim(),
      format: form.format.trim(),
      due_date: form.due_date ? form.due_date : undefined,
      priority: Number(form.priority) || 0,
      work_nominal_min: Number(form.work_nominal_min) || 60,
    });

    setShowAdd(false);
    setForm({ of_id: '', format: 'F1', due_date: '', priority: 5, work_nominal_min: 60 });

    await handleReload();
  };

  const handleRecompute = async () => {
    await api.recomputePlan(strategy);
    await planPoll.refetch();
    // si tu veux aussi voir l’impact côté OF list :
    await woPoll.refetch();
  };

  return (
    <div className="space-y-6">
      <Card title="Planning & OF (Ordres de fabrication)">
        <div className="flex flex-wrap gap-3 items-end justify-between mb-4">
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={tab === 'orders' ? 'primary' : 'secondary'}
              onClick={() => setTab('orders')}
            >
              OF (Work Orders)
            </Button>
            <Button
              size="sm"
              variant={tab === 'schedule' ? 'primary' : 'secondary'}
              onClick={() => setTab('schedule')}
            >
              Ordonnancement (Preview)
            </Button>
          </div>

          <div className="flex gap-2 items-end flex-wrap">
            {tab === 'schedule' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Limit</label>
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

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Strategy
                  </label>
                  <select
                    value={strategy}
                    onChange={(e) => setStrategy(e.target.value as any)}
                    className="border rounded px-3 py-2"
                  >
                    <option value="FORMAT_PRIORITY">Format → Priority</option>
                    <option value="EDD_SETUP">EDD + Setup</option>
                  </select>
                </div>

                <Button size="sm" variant="secondary" onClick={handleRecompute} disabled={active.loading}>
                  <Shuffle className="w-4 h-4 mr-1 inline" />
                  Recompute
                </Button>
              </>
            )}

            <Button size="sm" variant="secondary" onClick={handleReload} disabled={active.loading}>
              <RefreshCw className="w-4 h-4 mr-1 inline" />
              Reload
            </Button>

            {tab === 'schedule' && (
              <Button size="sm" onClick={handleDownloadCSV}>
                <Download className="w-4 h-4 mr-1 inline" />
                Download CSV
              </Button>
            )}

            <Button size="sm" onClick={() => setShowAdd(true)}>
              <Plus className="w-4 h-4 mr-1 inline" />
              Ajouter un OF
            </Button>
          </div>
        </div>

        {showAdd && (
          <div className="border rounded-lg p-4 bg-gray-50 mb-5">
            <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">OF ID</label>
                <input
                  value={form.of_id}
                  onChange={(e) => setForm((s) => ({ ...s, of_id: e.target.value }))}
                  className="border rounded px-3 py-2 w-full"
                  placeholder="OF00012"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
                <select
                  value={form.format}
                  onChange={(e) => setForm((s) => ({ ...s, format: e.target.value }))}
                  className="border rounded px-3 py-2 w-full"
                >
                  {['F1', 'F2', 'F3', 'F4', 'F5', 'F6'].map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Due date (optional)</label>
                <input
                  value={form.due_date}
                  onChange={(e) => setForm((s) => ({ ...s, due_date: e.target.value }))}
                  className="border rounded px-3 py-2 w-full"
                  placeholder="2026-01-07T16:00"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                <input
                  type="number"
                  value={form.priority}
                  onChange={(e) => setForm((s) => ({ ...s, priority: Number(e.target.value) }))}
                  className="border rounded px-3 py-2 w-full"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Work nominal (min)
                </label>
                <input
                  type="number"
                  value={form.work_nominal_min}
                  onChange={(e) =>
                    setForm((s) => ({ ...s, work_nominal_min: Number(e.target.value) }))
                  }
                  className="border rounded px-3 py-2 w-full"
                />
              </div>
            </div>

            <div className="mt-3 flex gap-2">
              <Button onClick={handleAdd} disabled={!canSubmit}>
                Ajouter
              </Button>
              <Button variant="secondary" onClick={() => setShowAdd(false)}>
                Annuler
              </Button>
            </div>
          </div>
        )}

        {active.loading ? (
          <LoadingSpinner size="lg" />
        ) : active.error ? (
          <ErrorMessage error={active.error} onRetry={active.refetch} />
        ) : tab === 'orders' && woPoll.data ? (
          woPoll.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">OF ID</th>
                    <th className="px-3 py-2 text-left">Format</th>
                    <th className="px-3 py-2 text-left">Due</th>
                    <th className="px-3 py-2 text-left">Priority</th>
                    <th className="px-3 py-2 text-left">Work (min)</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {woPoll.data.map((wo, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{wo.of_id}</td>
                      <td className="px-3 py-2">{wo.format}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{wo.due_date ? formatDateTime(wo.due_date) : '-'}</td>
                      <td className="px-3 py-2">{wo.priority}</td>
                      <td className="px-3 py-2">{wo.work_nominal_min}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              Aucun OF. Clique sur “Ajouter un OF”.
            </div>
          )
        ) : tab === 'schedule' && planPoll.data ? (
          planPoll.data.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">OF ID</th>
                    <th className="px-3 py-2 text-left">Format</th>
                    <th className="px-3 py-2 text-left">Start</th>
                    <th className="px-3 py-2 text-left">End</th>
                    <th className="px-3 py-2 text-left">Setup</th>
                    <th className="px-3 py-2 text-left">Work</th>
                    <th className="px-3 py-2 text-left">Note</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {planPoll.data.map((item, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{item.of_id}</td>
                      <td className="px-3 py-2">{item.format}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.start)}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{formatDateTime(item.end)}</td>
                      <td className="px-3 py-2">{formatDuration(item.setup_min)}</td>
                      <td className="px-3 py-2">{formatDuration(item.work_nominal_min)}</td>
                      <td className="px-3 py-2 text-xs text-gray-600">{item.note || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-gray-500 py-8">
              Clique “Reload” puis “Recompute” pour voir l’ordonnancement.
            </div>
          )
        ) : (
          <div className="text-center text-gray-500 py-8">
            Clique “Reload” pour charger les données.
          </div>
        )}
      </Card>
    </div>
  );
}
