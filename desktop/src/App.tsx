import { useState, useEffect } from 'react';
import { Send, Sparkles, Settings } from 'lucide-react';
import Sidebar from './components/Sidebar';
import Editor from './components/Editor';
import Terminal, { LogEntry } from './components/Terminal';

const INITIAL_LOGS: LogEntry[] = [
  { id: 1, tool: 'terminal', command: 'git status', status: 'completed', result: 'On branch main. Nothing to commit.', ts: '17:10:01' },
  { id: 2, tool: 'python_exec', command: 'python3 -c "import fastapi"', status: 'completed', result: 'FastAPI available.', ts: '17:10:03' },
  { id: 3, tool: 'vortex_agent', command: 'Initialising backend...', status: 'running', result: 'Waiting for localhost:8000...', ts: '17:10:05' },
];

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>(INITIAL_LOGS);

  // Simulate the initial "running" entry completing after 3 s
  useEffect(() => {
    const t = setTimeout(() => {
      setLogs((prev) =>
        prev.map((l) =>
          l.id === 3 ? { ...l, status: 'completed', result: 'Backend ready at http://localhost:8000' } : l
        )
      );
    }, 3000);
    return () => clearTimeout(t);
  }, []);

  const now = () =>
    new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const handleSend = async () => {
    if (!prompt.trim()) return;
    const id = Date.now();
    const userPrompt = prompt;
    setPrompt('');
    setLogs((prev) => [
      ...prev,
      { id, tool: 'vortex_agent', command: userPrompt, status: 'running', result: 'Processing instruction…', ts: now() },
    ]);

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userPrompt }),
      });
      const data = await res.json();
      setLogs((prev) =>
        prev.map((l) =>
          l.id === id ? { ...l, status: 'completed', result: data.response ?? 'Done.' } : l
        )
      );
    } catch {
      setLogs((prev) =>
        prev.map((l) =>
          l.id === id ? { ...l, status: 'error', result: 'Backend not reachable (localhost:8000)' } : l
        )
      );
    }
  };

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Title bar / header */}
      <header className="flex items-center gap-3 px-4 py-2 bg-zinc-900 border-b border-zinc-700/50 drag-region" style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}>
        {/* macOS traffic light space */}
        <span className="w-16 shrink-0" />
        <Sparkles size={16} className="text-indigo-400" />
        <span className="text-sm font-semibold text-zinc-200 select-none">Vortex Agent</span>
        <span className="ml-auto" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
          <button className="p-1.5 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors">
            <Settings size={15} />
          </button>
        </span>
      </header>

      {/* 3-pane workspace */}
      <div className="flex flex-1 min-h-0">
        <Sidebar />
        <div className="flex flex-col flex-1 min-w-0 relative">
          <Editor />

          {/* Floating command bar */}
          <div className="absolute bottom-0 left-0 right-0 p-4">
            <div className="flex items-center gap-2 bg-zinc-800/90 backdrop-blur border border-zinc-600/50 rounded-xl px-3 py-2 shadow-2xl">
              <Sparkles size={14} className="text-indigo-400 shrink-0" />
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask Vortex Agent anything…"
                className="flex-1 bg-transparent text-sm text-zinc-200 placeholder-zinc-500 outline-none"
              />
              <button
                onClick={handleSend}
                disabled={!prompt.trim()}
                className="p-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Send size={13} />
              </button>
            </div>
          </div>
        </div>
        <Terminal logs={logs} />
      </div>
    </div>
  );
}
