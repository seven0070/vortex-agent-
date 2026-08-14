import { useMemo, useState } from 'react';
import { Panel } from '../components/Panel';
import { usePolling } from '../hooks/usePolling';
import { createApi } from '../services/api';
import { useAppStore } from '../stores/AppStore';

const metrics = ['CPU', 'RAM', 'Tasks', 'Agents', 'Tool calls', 'Latency', 'Errors', 'Memory hits'];
const dimensions = ['Reasoning', 'Planning', 'Memory', 'Coding', 'Tools', 'Reliability', 'Safety', 'Coordination'];

export function BenchmarksPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [obs, setObs] = useState<any>({});
  const [stats, setStats] = useState<any>({});

  usePolling(async () => {
    const [o, s] = await Promise.all([api.observability(), api.stats()]);
    setObs(o ?? {});
    setStats(s ?? {});
  }, 4000);

  return (
    <div className="page grid-2">
      <Panel title="Observability">
        <ul className="check-list">
          {metrics.map((m) => (
            <li key={m}>{m}: {String(obs?.metrics?.[m.toLowerCase().replace(' ', '_')] ?? 'n/a')}</li>
          ))}
        </ul>
      </Panel>
      <Panel title="Benchmarks">
        <ul className="check-list">
          {dimensions.map((d) => (
            <li key={d}>{d}: {String(stats?.[d.toLowerCase()] ?? 'n/a')}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
