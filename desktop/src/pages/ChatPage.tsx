import { useMemo, useState } from 'react';
import { createBackendBridge } from '../services/backendBridge';
import { useAppStore } from '../stores/AppStore';
import type { ChatMessage } from '../types/models';

export function ChatPage() {
  const { backendPort } = useAppStore();
  const bridge = useMemo(() => createBackendBridge(backendPort), [backendPort]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);
  const [lastPrompt, setLastPrompt] = useState('');
  const [controller, setController] = useState<AbortController | null>(null);

  const onSend = async (retryText?: string) => {
    const text = (retryText ?? prompt).trim();
    if (!text || busy) return;
    setBusy(true);
    setPrompt('');
    setLastPrompt(text);
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    const nextController = new AbortController();
    setController(nextController);
    let assistant = '';
    setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);
    try {
      await bridge.sendChatStream(
        text,
        (delta) => {
          assistant += delta;
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { role: 'assistant', content: assistant };
            return copy;
          });
        },
        { orchestrated: true, signal: nextController.signal },
      );
    } catch (error) {
      const content = error instanceof Error ? error.message : 'Chat failed';
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: 'assistant', content };
        return copy;
      });
    } finally {
      setBusy(false);
      setController(null);
    }
  };

  return (
    <div className="page">
      <div className="prompt-row">
        <button type="button" onClick={() => setMessages([])} disabled={busy}>
          New Conversation
        </button>
        <button type="button" onClick={() => controller?.abort()} disabled={!busy || !controller}>
          Stop
        </button>
        <button type="button" onClick={() => void onSend(lastPrompt)} disabled={busy || !lastPrompt}>
          Retry
        </button>
      </div>
      <div className="conversation">
        {messages.length === 0 && <p className="muted">Conversation</p>}
        {messages.map((message, idx) => (
          <div key={`${message.role}-${idx}`} className={`chat-bubble ${message.role}`}>
            <strong>{message.role === 'user' ? 'You' : 'Vortex'}:</strong> {message.content}
            {message.role === 'assistant' && message.content && (
              <button
                type="button"
                className="ghost-button"
                onClick={() => void navigator.clipboard.writeText(message.content)}
              >
                Copy
              </button>
            )}
          </div>
        ))}
      </div>
      <div className="prompt-row">
        <input
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask Vortex..."
          onKeyDown={(e) => e.key === 'Enter' && void onSend()}
        />
        <button type="button" onClick={() => void onSend()} disabled={busy || !prompt.trim()}>
          {busy ? 'Sending...' : 'Send'}
        </button>
      </div>
    </div>
  );
}
