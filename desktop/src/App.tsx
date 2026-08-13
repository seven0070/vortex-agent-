import { useEffect, useMemo, useState } from 'react';
import { Send, Sparkles } from 'lucide-react';
import Editor from './components/Editor';
import Sidebar, { type SidebarTab } from './components/Sidebar';
import Terminal from './components/Terminal';
import { chat, fetchMemory, fetchOrchestration, fetchTools, type ToolExecution } from './api/client';

export default function App() {
  const [activeTab, setActiveTab] = useState<SidebarTab>('files');
  const [prompt, setPrompt] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [memories, setMemories] = useState<string[]>([]);
  const [logs, setLogs] = useState<ToolExecution[]>([
    {
      id: 1,
      command: 'Backend bootstrap',
      tool: 'vortex-backend',
      status: 'completed',
      result: 'Desktop connected to http://localhost:8000',
    },
  ]);

  useEffect(() => {
    const loadSidebarData = async () => {
      try {
        const [toolNames, memoryEntries] = await Promise.all([fetchTools(), fetchMemory()]);
        setSkills(toolNames);
        setMemories(memoryEntries.slice(0, 10));
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown sidebar load error';
        setLogs((current) => [
          {
            id: Date.now(),
            command: 'Fetch sidebar data',
            tool: 'api',
            status: 'failed',
            result: message,
          },
          ...current,
        ]);
      }
    };

    void loadSidebarData();
  }, []);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const states = await fetchOrchestration();
        const newest = states[0];
        if (!newest) {
          return;
        }

        setLogs((current) => {
          const summary = `${newest.goal ?? 'orchestration task'} → ${newest.final_outcome ?? 'running'}`;
          const alreadyAdded = current.some((entry) => entry.command === summary);
          if (alreadyAdded) {
            return current;
          }
          const status: ToolExecution['status'] = newest.final_outcome ? 'completed' : 'running';

          return [
            {
              id: Date.now(),
              command: summary,
              tool: 'orchestration',
              status,
              result: newest.id ?? 'state update',
            },
            ...current,
          ].slice(0, 60);
        });
      } catch {
        // keep stream stable if polling fails intermittently
      }
    }, 4000);

    return () => clearInterval(interval);
  }, []);

  const canSend = useMemo(() => prompt.trim().length > 0, [prompt]);

  const handleSend = async () => {
    const message = prompt.trim();
    if (!message) {
      return;
    }

    const id = Date.now();
    setLogs((current) => [
      {
        id,
        command: message,
        tool: 'chat',
        status: 'running',
        result: 'Sending prompt to /api/chat ...',
      },
      ...current,
    ]);

    setPrompt('');

    try {
      const response = await chat(message);
      setLogs((current) =>
        current.map((entry) =>
          entry.id === id
            ? { ...entry, status: 'completed', result: response || 'No response payload returned.' }
            : entry,
        ),
      );
    } catch (error) {
      const messageText = error instanceof Error ? error.message : 'Unknown chat error';
      setLogs((current) =>
        current.map((entry) =>
          entry.id === id ? { ...entry, status: 'failed', result: messageText } : entry,
        ),
      );
    }
  };

  const handleAccept = () => {
    setLogs((current) => [
      {
        id: Date.now(),
        command: 'Accept diff',
        tool: 'review',
        status: 'completed',
        result: 'Diff accepted in workspace preview.',
      },
      ...current,
    ]);
  };

  const handleReject = () => {
    setLogs((current) => [
      {
        id: Date.now(),
        command: 'Reject diff',
        tool: 'review',
        status: 'completed',
        result: 'Diff rejected in workspace preview.',
      },
      ...current,
    ]);
  };

  return (
    <main className="h-screen bg-zinc-950 text-zinc-100">
      <section className="grid h-full grid-cols-1 lg:grid-cols-[280px_1fr_360px]">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} skills={skills} memories={memories} />

        <div className="relative min-w-0 overflow-hidden">
          <Editor onAccept={handleAccept} onReject={handleReject} />

          <div className="pointer-events-none absolute inset-x-0 bottom-0 p-4">
            <form
              className="pointer-events-auto mx-auto flex max-w-4xl items-center gap-2 rounded-xl border border-zinc-700/70 bg-zinc-900/95 p-2 shadow-xl"
              onSubmit={(event) => {
                event.preventDefault();
                void handleSend();
              }}
            >
              <Sparkles className="ml-2 h-4 w-4 shrink-0 text-indigo-300" />
              <input
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder="Ask Vortex Agent to run or explain something..."
                className="h-10 flex-1 border-0 bg-transparent px-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-500"
              />
              <button
                type="submit"
                disabled={!canSend}
                className="inline-flex h-10 items-center gap-2 rounded-lg bg-indigo-500 px-4 text-sm font-medium text-indigo-50 disabled:cursor-not-allowed disabled:bg-zinc-700"
              >
                <Send className="h-4 w-4" />
                Send
              </button>
            </form>
          </div>
        </div>

        <Terminal logs={logs} />
      </section>
    </main>
  );
}
