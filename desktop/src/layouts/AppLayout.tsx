import type { ReactNode } from 'react';
import { Sidebar } from '../components/Sidebar';
import { TopBar } from '../components/TopBar';
import { useAppStore } from '../stores/AppStore';

export function AppLayout({ children }: { children: ReactNode }) {
  const { route, setRoute } = useAppStore();
  return (
    <main className="app-shell">
      <TopBar />
      <div className="content-shell">
        <Sidebar route={route} onRoute={setRoute} />
        <section className="content">{children}</section>
      </div>
    </main>
  );
}
