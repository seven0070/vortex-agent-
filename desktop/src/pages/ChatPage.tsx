import { useMemo, useState } from 'react';
import { createApi } from '../services/api';
import { useAppStore } from '../stores/AppStore';
import type { ChatMessage } from '../types/models';

export function ChatPage() {
  const { backendPort } = useAppStore();
  const api = useMemo(() => createApi(backendPort), [backendPort]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [prompt, setPrompt] = useState('');
  const [busy, setBusy] = useState(false);

  const onSend = async () => {
    const text = prompt.trim();
    if (!text || busy) return;
    setBusy(true);
    setPrompt('');
    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    try {
      const res = await api.chat(text, true);
      setMessages((prev) => [...prev, { role: 'assistant', content: res.response ?? '' }]);
    } catch (error) {
      const content = error instanceof Error ? error.message : 'Chat failed';
      setMessages((prev) => [...prev, { role: 'assistant', content }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="conversation">
        {messages.length === 0 && <p className="muted">Conversation</p>}
        {messages.map((message, idx) => (
          <div key={`${message.role}-${idx}`} className={`chat-bubble ${message.role}`}>
            <strong>{message.role === 'user' ? 'You' : 'Vortex'}:</strong> {message.content}
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
