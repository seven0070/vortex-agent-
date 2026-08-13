import { useState } from 'react';
import { FolderTree, BookOpen, Cpu, ChevronRight, File, Folder } from 'lucide-react';

type Tab = 'files' | 'skills' | 'memory';

const FILES = [
  { name: 'backend', type: 'folder', children: ['main.py', 'memory.py', 'skills.py', 'council.py'] },
  { name: 'README.md', type: 'file' },
  { name: 'requirements.txt', type: 'file' },
];

const SKILLS = [
  { name: 'terminal_exec', desc: 'Execute shell commands' },
  { name: 'python_exec', desc: 'Run Python scripts' },
  { name: 'web_search', desc: 'Search the web' },
  { name: 'file_read', desc: 'Read file contents' },
  { name: 'file_write', desc: 'Write to files' },
  { name: 'git_ops', desc: 'Git operations' },
];

const MEMORIES = [
  { key: 'project_root', value: '/vortex-agent' },
  { key: 'backend_port', value: '8000' },
  { key: 'last_task', value: 'Create desktop app' },
];

export default function Sidebar() {
  const [activeTab, setActiveTab] = useState<Tab>('files');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ backend: true });

  const tabs: { id: Tab; icon: React.ReactNode; label: string }[] = [
    { id: 'files', icon: <FolderTree size={16} />, label: 'Files' },
    { id: 'skills', icon: <BookOpen size={16} />, label: 'Skills' },
    { id: 'memory', icon: <Cpu size={16} />, label: 'Memory' },
  ];

  return (
    <aside className="flex flex-col h-full bg-zinc-900 border-r border-zinc-700/50 w-64 min-w-[220px] select-none">
      {/* Tab bar */}
      <div className="flex border-b border-zinc-700/50">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-xs font-medium transition-colors
              ${activeTab === t.id
                ? 'text-indigo-400 border-b-2 border-indigo-500 bg-zinc-800/50'
                : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-2 text-sm">
        {activeTab === 'files' && (
          <div className="space-y-0.5">
            {FILES.map((item) =>
              item.type === 'folder' ? (
                <div key={item.name}>
                  <button
                    onClick={() => setExpanded((e) => ({ ...e, [item.name]: !e[item.name] }))}
                    className="flex items-center gap-1.5 w-full px-2 py-1 rounded hover:bg-zinc-800 text-zinc-300"
                  >
                    <ChevronRight
                      size={12}
                      className={`transition-transform ${expanded[item.name] ? 'rotate-90' : ''}`}
                    />
                    <Folder size={14} className="text-yellow-400/80" />
                    <span>{item.name}</span>
                  </button>
                  {expanded[item.name] && item.children?.map((child) => (
                    <div key={child} className="flex items-center gap-1.5 pl-7 pr-2 py-1 rounded hover:bg-zinc-800 text-zinc-400 cursor-pointer">
                      <File size={12} />
                      <span>{child}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div key={item.name} className="flex items-center gap-1.5 px-2 py-1 rounded hover:bg-zinc-800 text-zinc-300 cursor-pointer">
                  <span className="w-3" />
                  <File size={14} className="text-zinc-500" />
                  <span>{item.name}</span>
                </div>
              )
            )}
          </div>
        )}

        {activeTab === 'skills' && (
          <div className="space-y-1">
            {SKILLS.map((s) => (
              <div key={s.name} className="px-2 py-1.5 rounded hover:bg-zinc-800 cursor-pointer">
                <p className="text-indigo-300 font-mono text-xs">{s.name}</p>
                <p className="text-zinc-500 text-xs mt-0.5">{s.desc}</p>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'memory' && (
          <div className="space-y-1">
            {MEMORIES.map((m) => (
              <div key={m.key} className="px-2 py-1.5 rounded hover:bg-zinc-800">
                <p className="text-zinc-400 text-xs">{m.key}</p>
                <p className="text-zinc-200 text-xs font-mono mt-0.5">{m.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
