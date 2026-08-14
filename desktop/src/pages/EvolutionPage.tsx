import { useMemo, useState } from 'react';
import { Panel } from '../components/Panel';
import { usePolling } from '../hooks/usePolling';
import { createApi } from '../services/api';
import { useAppStore } from '../stores/AppStore';

export function EvolutionPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [generations, setGenerations] = useState<any[]>([]);
  const [evals, setEvals] = useState<any[]>([]);

  usePolling(async () => {
    const [g, e] = await Promise.all([api.rsiGenerations(), api.rsiEvals()]);
    setGenerations(Array.isArray(g) ? g : []);
    setEvals(Array.isArray(e) ? e : []);
  }, 5000);

  const current = generations[0];
  const candidate = generations[1];

  return (
    <div className="page grid-2">
      <Panel title="Current vs Candidate">
        <div className="evolution-grid">
          <div>
            <div className="muted">CURRENT</div>
            <div>Vortex v{current?.generation ?? '---'}</div>
            <div className="status-chip ok">Stable</div>
          </div>
          <div>
            <div className="muted">CANDIDATE</div>
            <div>Vortex v{candidate?.generation ?? '---'}</div>
            <ul className="check-list">
              <li>Tests ✓</li>
              <li>Benchmark ✓</li>
              <li>Security ✓</li>
              <li>Governance ✓</li>
              <li>Canary ●</li>
            </ul>
            <div className="row">
              <button type="button">Reject</button>
              <button type="button">Promote</button>
            </div>
          </div>
        </div>
      </Panel>
      <Panel title="Evolution Logs">
        <pre className="json-view">{JSON.stringify({ generations, evals }, null, 2)}</pre>
      </Panel>
    </div>
  );
}
