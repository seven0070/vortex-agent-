import type { VortexRoute } from '../types/models';

type Props = {
  route: VortexRoute;
  onRoute: (route: VortexRoute) => void;
};

const links: Array<{ label: string; route: VortexRoute }> = [
  { label: 'New Task', route: 'new-task' },
  { label: 'Chat', route: 'chat' },
  { label: 'Missions', route: 'missions' },
  { label: 'Council', route: 'council' },
  { label: 'Resolution', route: 'resolution' },
  { label: 'Memory', route: 'memory' },
  { label: 'Knowledge', route: 'knowledge' },
  { label: 'Tools', route: 'tools' },
  { label: 'Governance', route: 'governance' },
  { label: 'Sovereign', route: 'sovereign' },
  { label: 'Evolution', route: 'evolution' },
  { label: 'Benchmarks', route: 'benchmarks' },
  { label: 'Settings', route: 'settings' },
];

export function Sidebar({ route, onRoute }: Props) {
  return (
    <aside className="sidebar">
      {links.map((link) => (
        <button
          key={`${link.label}-${link.route}`}
          className={`sidebar-link ${route === link.route ? 'active' : ''}`}
          onClick={() => onRoute(link.route)}
          type="button"
        >
          {link.label}
        </button>
      ))}
    </aside>
  );
}
