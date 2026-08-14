export const VORTEX_ROUTES = [
  'new-task',
  'chat',
  'missions',
  'council',
  'resolution',
  'memory',
  'knowledge',
  'governance',
  'sovereign',
  'tools',
  'evolution',
  'benchmarks',
  'settings',
] as const;

export type VortexRoute = (typeof VORTEX_ROUTES)[number];

export type AppTheme = 'dark' | 'light';

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
};

export type MissionStage = {
  name: string;
  status: 'pending' | 'completed' | 'active';
};

export type MissionView = {
  id: string;
  goal: string;
  stages: MissionStage[];
};

export type HealthStatus = {
  status?: string;
  bots?: number;
  generation?: number;
  sovereign_mode?: string;
};
