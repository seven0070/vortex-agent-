import axios from 'axios';

const backendPort = (window as Window & { electronAPI?: { backendPort?: string } }).electronAPI?.backendPort ?? '8000';
const api = axios.create({
  baseURL: `http://localhost:${backendPort}`,
  timeout: 20000,
});

export type ToolExecution = {
  id: number;
  command: string;
  tool: string;
  status: 'running' | 'completed' | 'failed';
  result: string;
};

export async function chat(message: string): Promise<string> {
  const { data } = await api.post<{ response: string }>('/api/chat', { message });
  return data.response ?? '';
}

export async function fetchTools(): Promise<string[]> {
  const { data } = await api.get<{ tools?: { name: string }[] }>('/api/tools');
  return (data.tools ?? []).map((tool) => tool.name);
}

export async function fetchMemory(): Promise<string[]> {
  const { data } = await api.get<{ recent_history?: Array<{ user: string; assistant: string }> }>('/api/memory');
  return (data.recent_history ?? []).map((entry) => entry.user || entry.assistant).filter(Boolean);
}

export async function fetchOrchestration(): Promise<Array<{ goal?: string; final_outcome?: string; id?: string }>> {
  const { data } = await api.get<Array<{ goal?: string; final_outcome?: string; id?: string }>>('/api/orchestration');
  return Array.isArray(data) ? data : [];
}
