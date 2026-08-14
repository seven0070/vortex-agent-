import { useMemo, useState } from 'react';
import { Panel } from '../components/Panel';
import { createBackendBridge } from '../services/backendBridge';
import { useAppStore } from '../stores/AppStore';

export function SettingsPage() {
  const { backendPort, setBackendStatus, setOnline } = useAppStore();
  const [busy, setBusy] = useState(false);
  const bridge = useMemo(() => createBackendBridge(backendPort), [backendPort]);

  const refresh = async () => {
    const [health, snapshot] = await Promise.allSettled([bridge.api.health(), bridge.lifecycleSnapshot()]);
    const online = health.status === 'fulfilled' && health.value?.status === 'healthy';
    const running = snapshot.status === 'fulfilled' ? !!snapshot.value.backend_running : false;
    const error = snapshot.status === 'fulfilled' ? snapshot.value.last_error ?? null : 'Backend unavailable';
    setOnline(online);
    setBackendStatus(running, error);
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      await refresh().catch(() => undefined);
      setBusy(false);
    }
  };

  return (
    <Panel title="Settings">
      <p className="muted">Backend API: http://127.0.0.1:{backendPort}</p>
      <p className="muted">Packaging mode: Tauri native shell.</p>
      <div className="prompt-row">
        <button type="button" disabled={busy} onClick={() => void run(() => bridge.reconnect().then(() => undefined))}>
          Reconnect Backend
        </button>
        <button type="button" disabled={busy} onClick={() => void run(() => bridge.safeShutdown())}>
          Shutdown Backend
        </button>
        <button type="button" disabled={busy} onClick={() => void run(() => refresh())}>
          Refresh Status
        </button>
      </div>
    </Panel>
  );
}
