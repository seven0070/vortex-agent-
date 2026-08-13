import { useState } from 'react';
import { Check, X, FileCode, GitBranch } from 'lucide-react';

const SAMPLE_DIFF = `--- a/backend/main.py
+++ b/backend/main.py
@@ -1,7 +1,10 @@
 from fastapi import FastAPI
+from fastapi.middleware.cors import CORSMiddleware
 import uvicorn

 app = FastAPI()
+app.add_middleware(
+    CORSMiddleware, allow_origins=["*"],
+    allow_methods=["*"], allow_headers=["*"]
+)

 @app.get("/health")
-def health():
-    return {"status": "ok"}
+def health():
+    return {"status": "ok", "version": "2.0"}`;

export default function Editor() {
  const [hasDiff, setHasDiff] = useState(true);
  const [accepted, setAccepted] = useState<boolean | null>(null);

  const handleAccept = () => {
    setAccepted(true);
    setHasDiff(false);
  };

  const handleReject = () => {
    setAccepted(false);
    setHasDiff(false);
  };

  return (
    <main className="flex flex-col h-full bg-zinc-950 flex-1 min-w-0 overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-700/50 bg-zinc-900/80">
        <FileCode size={14} className="text-indigo-400" />
        <span className="text-sm text-zinc-300 font-mono">backend/main.py</span>
        {hasDiff && (
          <span className="ml-auto flex items-center gap-1.5">
            <span className="text-xs text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded-full flex items-center gap-1">
              <GitBranch size={10} /> diff pending
            </span>
          </span>
        )}
        {accepted === true && (
          <span className="ml-auto text-xs text-emerald-400">✓ Changes accepted</span>
        )}
        {accepted === false && (
          <span className="ml-auto text-xs text-red-400">✗ Changes rejected</span>
        )}
      </div>

      {/* Diff viewer */}
      <div className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-6">
        {SAMPLE_DIFF.split('\n').map((line, i) => {
          let cls = 'text-zinc-400';
          if (line.startsWith('+') && !line.startsWith('+++')) cls = 'text-emerald-400 bg-emerald-500/10';
          else if (line.startsWith('-') && !line.startsWith('---')) cls = 'text-red-400 bg-red-500/10';
          else if (line.startsWith('@@')) cls = 'text-cyan-400 bg-cyan-500/10';
          else if (line.startsWith('---') || line.startsWith('+++')) cls = 'text-zinc-500';
          return (
            <div key={i} className={`px-2 rounded ${cls}`}>
              <span className="select-none text-zinc-600 mr-4 inline-block w-6 text-right">{i + 1}</span>
              {line || ' '}
            </div>
          );
        })}
      </div>

      {/* Accept / Reject bar */}
      {hasDiff && (
        <div className="flex items-center justify-end gap-3 px-4 py-3 border-t border-zinc-700/50 bg-zinc-900/80">
          <button
            onClick={handleReject}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-red-500/15 text-red-400 text-sm hover:bg-red-500/30 transition-colors"
          >
            <X size={14} /> Reject
          </button>
          <button
            onClick={handleAccept}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-emerald-500/20 text-emerald-400 text-sm hover:bg-emerald-500/35 transition-colors"
          >
            <Check size={14} /> Accept
          </button>
        </div>
      )}
    </main>
  );
}
