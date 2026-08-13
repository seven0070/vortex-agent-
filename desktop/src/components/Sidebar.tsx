import { Brain, FolderTree, History, Sparkles } from 'lucide-react';

export type SidebarTab = 'files' | 'skills' | 'memory';

type SidebarProps = {
  activeTab: SidebarTab;
  onTabChange: (tab: SidebarTab) => void;
  skills: string[];
  memories: string[];
};

const tabs: Array<{ key: SidebarTab; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { key: 'files', label: 'Files', icon: FolderTree },
  { key: 'skills', label: 'Skills', icon: Sparkles },
  { key: 'memory', label: 'Memory', icon: Brain },
];

export default function Sidebar({ activeTab, onTabChange, skills, memories }: SidebarProps) {
  const files = ['vortex-agent/backend/main.py', 'vortex-agent/backend/orchestrator.py', 'vortex-agent/backend/memory.py'];

  return (
    <aside className="flex h-full w-full flex-col border-r border-zinc-800 bg-zinc-950">
      <div className="border-b border-zinc-800 px-4 py-3 text-sm font-semibold text-zinc-200">Workspace</div>
      <div className="grid grid-cols-3 gap-1 p-2">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            type="button"
            onClick={() => onTabChange(key)}
            className={`flex items-center justify-center gap-2 rounded-md px-2 py-2 text-xs transition ${
              activeTab === key ? 'bg-indigo-500/20 text-indigo-300' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-3 text-xs text-zinc-300">
        {activeTab === 'files' && (
          <ul className="space-y-2">
            {files.map((file) => (
              <li key={file} className="rounded border border-zinc-800 bg-zinc-900/40 p-2">
                {file}
              </li>
            ))}
          </ul>
        )}

        {activeTab === 'skills' && (
          <ul className="space-y-2">
            {skills.length === 0 && <li className="text-zinc-500">No skills loaded yet.</li>}
            {skills.map((skill) => (
              <li key={skill} className="rounded border border-zinc-800 bg-zinc-900/40 p-2">
                {skill}
              </li>
            ))}
          </ul>
        )}

        {activeTab === 'memory' && (
          <ul className="space-y-2">
            {memories.length === 0 && <li className="text-zinc-500">No recent memory yet.</li>}
            {memories.map((memory, index) => (
              <li key={`${memory}-${index}`} className="rounded border border-zinc-800 bg-zinc-900/40 p-2">
                <History className="mr-2 inline h-3.5 w-3.5 text-zinc-500" />
                {memory}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
