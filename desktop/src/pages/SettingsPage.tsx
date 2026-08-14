import { Panel } from '../components/Panel';
import { useAppStore } from '../stores/AppStore';

export function SettingsPage() {
  const { backendPort } = useAppStore();
  return (
    <Panel title="Settings">
      <p className="muted">Backend API: http://127.0.0.1:{backendPort}</p>
      <p className="muted">Packaging mode: Tauri native shell.</p>
    </Panel>
  );
}
