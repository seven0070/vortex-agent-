import { invoke } from '@tauri-apps/api/core';
import React, { createContext, useContext, useEffect, useMemo, useReducer } from 'react';
import type { AppTheme, VortexRoute } from '../types/models';

type State = {
  route: VortexRoute;
  theme: AppTheme;
  backendPort: number;
  online: boolean;
  backendRunning: boolean;
};

type Action =
  | { type: 'route'; route: VortexRoute }
  | { type: 'theme'; theme: AppTheme }
  | { type: 'port'; port: number }
  | { type: 'online'; online: boolean }
  | { type: 'backend'; running: boolean };

const initialState: State = {
  route: 'chat',
  theme: 'dark',
  backendPort: 8765,
  online: false,
  backendRunning: false,
};

function parseRoute(hash: string): VortexRoute {
  const candidate = hash.replace('#/', '') as VortexRoute;
  const routes: VortexRoute[] = [
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
  ];
  return routes.includes(candidate) ? candidate : 'chat';
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'route':
      return { ...state, route: action.route };
    case 'theme':
      return { ...state, theme: action.theme };
    case 'port':
      return { ...state, backendPort: action.port };
    case 'online':
      return { ...state, online: action.online };
    case 'backend':
      return { ...state, backendRunning: action.running };
    default:
      return state;
  }
}

type ContextValue = State & {
  setRoute: (route: VortexRoute) => void;
  toggleTheme: () => void;
  setOnline: (online: boolean) => void;
  setBackendRunning: (running: boolean) => void;
};

const AppContext = createContext<ContextValue | undefined>(undefined);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, {
    ...initialState,
    route: parseRoute(window.location.hash),
  });

  useEffect(() => {
    invoke<number>('get_backend_port')
      .then((port) => dispatch({ type: 'port', port }))
      .catch(() => undefined);

    invoke<{ backend_running: boolean }>('lifecycle_snapshot')
      .then((snapshot) => dispatch({ type: 'backend', running: !!snapshot.backend_running }))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    const onHash = () => dispatch({ type: 'route', route: parseRoute(window.location.hash) });
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = state.theme;
  }, [state.theme]);

  const value = useMemo<ContextValue>(
    () => ({
      ...state,
      setRoute: (route) => {
        window.location.hash = `/${route}`;
        dispatch({ type: 'route', route });
      },
      toggleTheme: () => dispatch({ type: 'theme', theme: state.theme === 'dark' ? 'light' : 'dark' }),
      setOnline: (online) => dispatch({ type: 'online', online }),
      setBackendRunning: (running) => dispatch({ type: 'backend', running }),
    }),
    [state],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useAppStore() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppStore must be used within AppProvider');
  return ctx;
}
