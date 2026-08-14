import { useMemo, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { Panel } from '../components/Panel';
import { createApi } from '../services/api';
import { useAppStore } from '../stores/AppStore';
import type { MissionView } from '../types/models';

const baseStages = ['Planning', 'Council', 'Resolution', 'Execution', 'Evaluation'];

export function MissionsPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [missions, setMissions] = useState<MissionView[]>([]);

  usePolling(async () => {
    try {
      const states = await api.orchestration();
      const mapped: MissionView[] = (Array.isArray(states) ? states : []).map((state: any, index: number) => {
        const active = state.final_outcome ? 'Evaluation' : 'Resolution';
        return {
          id: state.id ?? String(index),
          goal: state.goal ?? 'Task',
          stages: baseStages.map((name) => ({
            name,
            status: name === active ? 'active' : baseStages.indexOf(name) < baseStages.indexOf(active) ? 'completed' : 'pending',
          })),
        };
      });
      setMissions(mapped.slice(0, 8));
    } catch {
      setMissions([]);
    }
  }, 3000);

  return (
    <div className="page grid-2">
      {missions.length === 0 && <Panel title="Missions">No active operations.</Panel>}
      {missions.map((mission) => (
        <Panel key={mission.id} title={mission.goal}>
          <div className="pipeline">
            {mission.stages.map((stage) => (
              <div key={`${mission.id}-${stage.name}`} className={`stage ${stage.status}`}>
                {stage.name}
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  );
}
