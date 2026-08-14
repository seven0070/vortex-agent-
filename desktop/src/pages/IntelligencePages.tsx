import { useMemo, useState } from 'react';
import { JsonView } from '../components/JsonView';
import { Panel } from '../components/Panel';
import { usePolling } from '../hooks/usePolling';
import { createApi } from '../services/api';
import { useAppStore } from '../stores/AppStore';

export function CouncilPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.council()), 4000);
  return <Panel title="Council"><JsonView value={data} /></Panel>;
}

export function ResolutionPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.stats()), 5000);
  return <Panel title="Resolution"><JsonView value={data} /></Panel>;
}

export function MemoryPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.memory()), 4000);
  return <Panel title="Memory"><JsonView value={data} /></Panel>;
}

export function KnowledgePage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [data, setData] = useState({});
  usePolling(async () => setData(await api.memoryGraph()), 4000);
  return <Panel title="Knowledge Graph"><JsonView value={data} /></Panel>;
}
