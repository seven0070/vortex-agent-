import { CheckCircle2, Loader2, TerminalSquare, XCircle } from 'lucide-react';
import type { ToolExecution } from '../api/client';

type TerminalProps = {
  logs: ToolExecution[];
};

function StatusIcon({ status }: { status: ToolExecution['status'] }) {
  if (status === 'completed') {
    return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
  }

  if (status === 'failed') {
    return <XCircle className="h-4 w-4 text-rose-400" />;
  }

  return <Loader2 className="h-4 w-4 animate-spin text-indigo-300" />;
}

export default function Terminal({ logs }: TerminalProps) {
  return (
    <aside className="flex h-full w-full flex-col border-l border-zinc-800 bg-zinc-950">
      <header className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3 text-sm font-semibold text-zinc-100">
        <TerminalSquare className="h-4 w-4 text-indigo-300" />
        Tool Execution Stream
      </header>
      <div className="min-h-0 flex-1 space-y-2 overflow-auto p-3">
        {logs.map((log) => (
          <article key={log.id} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-xs">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="truncate font-medium text-zinc-200">{log.command}</span>
              <span className="flex items-center gap-1 text-zinc-400">
                <StatusIcon status={log.status} />
                {log.status}
              </span>
            </div>
            <div className="mb-1 text-zinc-500">tool: {log.tool}</div>
            <pre className="whitespace-pre-wrap break-words text-zinc-300">{log.result}</pre>
          </article>
        ))}
      </div>
    </aside>
  );
}
