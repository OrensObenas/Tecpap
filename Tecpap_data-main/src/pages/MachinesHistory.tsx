import { useEffect, useMemo, useState } from 'react';
import { api } from '../services/api';
import { Card } from '../components/Card';
import { Button } from '../components/Button';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { ErrorMessage } from '../components/ErrorMessage';
import { formatDateTime } from '../utils/formatters';
import type { MachineHistory, MachineState } from '../types/api';

type ViewMode = 'history' | 'state';

export function MachinesHistory() {
  const [history, setHistory] = useState<MachineHistory[]>([]);
  const [machinesState, setMachinesState] = useState<MachineState[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>('history');
  const [machineFilter, setMachineFilter] = useState<string>('');
  const [formatFilter, setFormatFilter] = useState<string>('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [histResp, stateResp] = await Promise.all([
        api.getMachineHistory(),
        api.getMachinesState(),
      ]);
      setHistory(histResp.items || []);
      setMachinesState(stateResp.items || []);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredHistory = useMemo(() => {
    return history.filter((h) => {
      const matchMachine = machineFilter ? h.machine_id === machineFilter : true;
      const matchFormat = formatFilter ? h.format === formatFilter : true;
      return matchMachine && matchFormat;
    });
  }, [history, machineFilter, formatFilter]);

  const summary = useMemo(() => {
    const byMachine: Record<string, { count: number; sum: number; best?: MachineHistory; worst?: MachineHistory }> =
      {};
    for (const h of history) {
      const bucket = byMachine[h.machine_id] || { count: 0, sum: 0 };
      bucket.count += 1;
      bucket.sum += Number(h.trs_percent || 0);
      if (!bucket.best || Number(h.trs_percent || 0) > Number(bucket.best.trs_percent || 0)) {
        bucket.best = h;
      }
      if (!bucket.worst || Number(h.trs_percent || 0) < Number(bucket.worst.trs_percent || 0)) {
        bucket.worst = h;
      }
      byMachine[h.machine_id] = bucket;
    }
    return Object.entries(byMachine).map(([machine_id, info]) => ({
      machine_id,
      avg: info.count > 0 ? (info.sum / info.count).toFixed(1) : '0',
      best: info.best,
      worst: info.worst,
    }));
  }, [history]);

  return (
    <div className="space-y-6">
      <Card title="Machines">
        <div className="flex flex-wrap gap-3 items-center mb-4">
          <Button
            size="sm"
            variant={view === 'history' ? 'primary' : 'secondary'}
            onClick={() => setView('history')}
          >
            Historique TRS
          </Button>
          <Button
            size="sm"
            variant={view === 'state' ? 'primary' : 'secondary'}
            onClick={() => setView('state')}
          >
            Etat en cours
          </Button>

          <div className="flex gap-2 items-end">
            <div>
              <label className="block text-sm text-gray-700 mb-1">Machine</label>
              <input
                value={machineFilter}
                onChange={(e) => setMachineFilter(e.target.value.trim())}
                className="border rounded px-3 py-2 text-sm w-28"
                placeholder="5"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-700 mb-1">Format</label>
              <input
                value={formatFilter}
                onChange={(e) => setFormatFilter(e.target.value.trim())}
                className="border rounded px-3 py-2 text-sm w-28"
                placeholder="F1"
              />
            </div>
          </div>

          <Button size="sm" variant="secondary" onClick={loadData} disabled={loading}>
            Reload
          </Button>
        </div>

        {loading ? (
          <LoadingSpinner size="lg" />
        ) : error ? (
          <ErrorMessage error={error} onRetry={loadData} />
        ) : view === 'state' ? (
          <MachinesStateTable items={machinesState} />
        ) : (
          <>
            <MachinesSummary items={summary} />
            <MachinesHistoryTable items={filteredHistory} />
          </>
        )}
      </Card>
    </div>
  );
}

function MachinesSummary({ items }: { items: { machine_id: string; avg: string; best?: MachineHistory; worst?: MachineHistory }[] }) {
  if (!items.length) {
    return (
      <div className="text-center text-gray-500 py-6">
        Aucun historique TRS.
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
      {items.map((it) => (
        <div key={it.machine_id} className="border rounded-lg p-3 bg-gray-50">
          <div className="text-sm text-gray-600">Machine</div>
          <div className="text-xl font-bold text-blue-700">{it.machine_id}</div>
          <div className="mt-1 text-sm">TRS moyen: <span className="font-semibold">{it.avg}%</span></div>
          <div className="text-xs text-gray-600 mt-1">
            Meilleur: {it.best ? `${it.best.format} (${it.best.trs_percent}%)` : '-'}
          </div>
          <div className="text-xs text-gray-600">
            Pire: {it.worst ? `${it.worst.format} (${it.worst.trs_percent}%)` : '-'}
          </div>
        </div>
      ))}
    </div>
  );
}

function MachinesHistoryTable({ items }: { items: MachineHistory[] }) {
  if (!items.length) {
    return (
      <div className="text-center text-gray-500 py-6">
        Aucun enregistrement. Ajoute `machine_history.csv`.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left">Machine</th>
            <th className="px-3 py-2 text-left">Format</th>
            <th className="px-3 py-2 text-left">TRS (%)</th>
            <th className="px-3 py-2 text-left">Samples</th>
            <th className="px-3 py-2 text-left">Avg setup (min)</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((it, idx) => (
            <tr key={idx} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium">{it.machine_id}</td>
              <td className="px-3 py-2">{it.format}</td>
              <td className="px-3 py-2">{it.trs_percent ?? '-'}</td>
              <td className="px-3 py-2">{it.sample_count ?? '-'}</td>
              <td className="px-3 py-2">{it.avg_setup_min ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MachinesStateTable({ items }: { items: MachineState[] }) {
  if (!items.length) {
    return (
      <div className="text-center text-gray-500 py-6">
        Pas d'état machine disponible.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-3 py-2 text-left">Machine</th>
            <th className="px-3 py-2 text-left">Disponible</th>
            <th className="px-3 py-2 text-left">Format courant</th>
            <th className="px-3 py-2 text-left">Running</th>
            <th className="px-3 py-2 text-left">Down</th>
            <th className="px-3 py-2 text-left">Speed</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((it, idx) => (
            <tr key={idx} className="hover:bg-gray-50">
              <td className="px-3 py-2 font-medium">{it.machine_id}</td>
              <td className="px-3 py-2 whitespace-nowrap">{it.available_from ? formatDateTime(it.available_from) : '-'}</td>
              <td className="px-3 py-2">{it.current_format || '-'}</td>
              <td className="px-3 py-2">{it.is_running ? 'YES' : 'NO'}</td>
              <td className="px-3 py-2">{it.is_down ? 'YES' : 'NO'}</td>
              <td className="px-3 py-2">{it.speed_factor ?? 1}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
