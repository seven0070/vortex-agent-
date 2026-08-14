import { useMemo, useState } from 'react';
import { JsonView } from '../components/JsonView';
import { Panel } from '../components/Panel';
import { usePolling } from '../hooks/usePolling';
import { createApi } from '../services/api';
import { useAppStore } from '../stores/AppStore';

export function GovernancePage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.governance()), 4000);
  return <Panel title="Governance"><JsonView value={data} /></Panel>;
}

export function SovereignPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.sovereign()), 4000);
  return <Panel title="Sovereign"><JsonView value={data} /></Panel>;
}

export function ToolsPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.tools()), 4000);
  return <Panel title="Tools"><JsonView value={data} /></Panel>;
}
