import React from 'react';
import { useMemo } from 'react';
import { AppLayout } from '../layouts/AppLayout';
import { ChatPage } from '../pages/ChatPage';
import { MissionsPage } from '../pages/MissionsPage';
import { CouncilPage, KnowledgePage, MemoryPage, ResolutionPage } from '../pages/IntelligencePages';
import { GovernancePage, SovereignPage, ToolsPage } from '../pages/ControlPages';
import { EvolutionPage } from '../pages/EvolutionPage';
import { BenchmarksPage } from '../pages/BenchmarksPage';
import { SettingsPage } from '../pages/SettingsPage';
import { createApi } from '../services/api';
import { usePolling } from '../hooks/usePolling';
import { useAppStore } from '../stores/AppStore';

export function App() {
  const { route, backendPort, setOnline } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);

  usePolling(async () => {
    try {
      const health = await api.health();
      setOnline(health?.status === 'healthy');
    } catch {
      setOnline(false);
    }
  }, 3000);

  let page: React.ReactElement;
  switch (route) {
    case 'missions':
      page = <MissionsPage />;
      break;
    case 'council':
      page = <CouncilPage />;
      break;
    case 'resolution':
      page = <ResolutionPage />;
      break;
    case 'memory':
      page = <MemoryPage />;
      break;
    case 'knowledge':
      page = <KnowledgePage />;
      break;
    case 'governance':
      page = <GovernancePage />;
      break;
    case 'sovereign':
      page = <SovereignPage />;
      break;
    case 'tools':
      page = <ToolsPage />;
      break;
    case 'evolution':
      page = <EvolutionPage />;
      break;
    case 'benchmarks':
      page = <BenchmarksPage />;
      break;
    case 'settings':
      page = <SettingsPage />;
      break;
    case 'chat':
    default:
      page = <ChatPage />;
      break;
  }

  return <AppLayout>{page}</AppLayout>;
}
