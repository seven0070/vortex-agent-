import axios from 'axios';

function baseURL(port: number) {
  return `http://127.0.0.1:${port}`;
}

export function createApi(port: number) {
  const api = axios.create({
    baseURL: baseURL(port),
    timeout: 20000,
  });

  return {
    health: () => api.get('/health').then((r) => r.data),
    chat: (message: string, orchestrated = true) => api.post('/api/chat', { message, orchestrated }).then((r) => r.data),
    orchestration: () => api.get('/api/orchestration').then((r) => r.data),
    council: () => api.get('/api/council').then((r) => r.data),
    governance: () => api.get('/api/governance').then((r) => r.data),
    sovereign: () => api.get('/api/sovereign').then((r) => r.data),
    tools: () => api.get('/api/tools').then((r) => r.data),
    memory: () => api.get('/api/memory').then((r) => r.data),
    memoryGraph: () => api.get('/api/memory/graph').then((r) => r.data),
    observability: () => api.get('/api/observability').then((r) => r.data),
    rsiGenerations: () => api.get('/api/rsi/generations').then((r) => r.data),
    rsiEvals: () => api.get('/api/rsi/evals').then((r) => r.data),
    stats: () => api.get('/api/stats').then((r) => r.data),
  };
}
