import { invoke } from '@tauri-apps/api/core';
import { createApi } from './api';

type StreamEvent = { type?: string; delta?: string };

export type LifecycleSnapshot = {
  backend_running: boolean;
  backend_port: number;
  last_error?: string | null;
};

export class BackendBridgeError extends Error {
  constructor(message: string, readonly cause?: unknown) {
    super(message);
    this.name = 'BackendBridgeError';
  }
}

export async function lifecycleSnapshot(): Promise<LifecycleSnapshot> {
  return invoke<LifecycleSnapshot>('lifecycle_snapshot');
}

export async function startBackend() {
  await invoke('start_backend');
}

export async function stopBackend() {
  await invoke('stop_backend');
}

export async function restartBackend() {
  await invoke('restart_backend');
}

async function streamRequest(url: string, body: unknown, onDelta: (delta: string) => void, signal?: AbortSignal) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error(`Stream request failed (${response.status})`);
  if (!response.body) throw new Error('No stream body returned');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      let event: StreamEvent;
      try {
        event = JSON.parse(trimmed) as StreamEvent;
      } catch {
        throw new Error('Received malformed stream payload');
      }
      if (event.type === 'chunk' && event.delta) onDelta(event.delta);
      if (event.type === 'error') throw new Error(event.delta ?? 'Stream failed');
    }
  }
}

export function createBackendBridge(port: number) {
  const api = createApi(port);
  const url = `http://127.0.0.1:${port}`;

  async function waitForHealth(retries = 12, delayMs = 500) {
    for (let i = 0; i < retries; i += 1) {
      try {
        const status = await api.health();
        if (status?.status === 'healthy') return true;
      } catch {
        // Ignore and retry.
      }
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
    return false;
  }

  return {
    api,
    lifecycleSnapshot,
    async reconnect() {
      await restartBackend();
      const ok = await waitForHealth();
      if (!ok) throw new BackendBridgeError('Backend failed to reconnect');
      return true;
    },
    async safeShutdown() {
      await stopBackend();
    },
    async sendChatStream(
      message: string,
      onDelta: (delta: string) => void,
      options?: { orchestrated?: boolean; signal?: AbortSignal },
    ) {
      const body = { message, orchestrated: options?.orchestrated ?? true };
      try {
        await streamRequest(`${url}/api/chat/stream`, body, onDelta, options?.signal);
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') throw error;
        const healthy = await waitForHealth(2, 400);
        if (!healthy) await this.reconnect();
        try {
          await streamRequest(`${url}/api/chat/stream`, body, onDelta, options?.signal);
        } catch {
          try {
            const fallback = await api.chat(message, body.orchestrated);
            if (fallback?.response) onDelta(String(fallback.response));
          } catch (finalError) {
            throw new BackendBridgeError('Failed to send chat request', finalError);
          }
        }
      }
    },
  };
}
