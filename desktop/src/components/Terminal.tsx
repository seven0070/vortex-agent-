import { useEffect, useRef } from 'react';
import { Terminal as TermIcon, CheckCircle, Loader, AlertCircle, XCircle } from 'lucide-react';

type Status = 'completed' | 'running' | 'error' | 'pending';

interface LogEntry {
  id: number;
  tool: string;
  command: string;
  status: Status;
  result: string;
  ts: string;
}

const STATUS_ICON: Record<Status, React.ReactNode> = {
  completed: <CheckCircle size={13} className="text-emerald-400 shrink-0" />,
  running: <Loader size={13} className="text-indigo-400 shrink-0 animate-spin" />,
  error: <XCircle size={13} className="text-red-400 shrink-0" />,
  pending: <AlertCircle size={13} className="text-amber-400 shrink-0" />,
};

export default function Terminal({ logs }: { logs: LogEntry[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when logs change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <aside className="flex flex-col h-full bg-zinc-900 border-l border-zinc-700/50 w-80 min-w-[260px]">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-700/50 bg-zinc-800/60">
        <TermIcon size={14} className="text-indigo-400" />
        <span className="text-xs font-medium text-zinc-300">Tool Execution Log</span>
        <span className="ml-auto text-xs text-zinc-500">{logs.length} entries</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {logs.map((log) => (
          <div
            key={log.id}
            className="rounded-md border border-zinc-700/40 bg-zinc-800/50 p-3 text-xs"
          >
            <div className="flex items-center gap-2 mb-1">
              {STATUS_ICON[log.status]}
              <span className="font-mono text-indigo-300">{log.tool}</span>
              <span className="ml-auto text-zinc-600">{log.ts}</span>
            </div>
            <p className="font-mono text-zinc-300 truncate">$ {log.command}</p>
            <p className="text-zinc-400 mt-1 leading-5">{log.result}</p>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </aside>
  );
}

export type { LogEntry };

