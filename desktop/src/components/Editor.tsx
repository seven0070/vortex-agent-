import { Check, GitCompare, X } from 'lucide-react';

type EditorProps = {
  diffText: string;
  onAccept: () => void;
  onReject: () => void;
};

export default function Editor({ diffText, onAccept, onReject }: EditorProps) {
  return (
    <section className="flex h-full w-full flex-col bg-zinc-950">
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-zinc-100">
          <GitCompare className="h-4 w-4 text-indigo-300" />
          Code / Diff Viewer
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onAccept}
            className="inline-flex items-center gap-1 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs text-emerald-300 hover:bg-emerald-500/20"
          >
            <Check className="h-3.5 w-3.5" /> Accept
          </button>
          <button
            type="button"
            onClick={onReject}
            className="inline-flex items-center gap-1 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/20"
          >
            <X className="h-3.5 w-3.5" /> Reject
          </button>
        </div>
      </header>

      <pre className="min-h-0 flex-1 overflow-auto bg-zinc-900/40 p-4 text-xs leading-relaxed text-zinc-300">{diffText}</pre>
    </section>
  );
}
