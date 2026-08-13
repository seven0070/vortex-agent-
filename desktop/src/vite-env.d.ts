/// <reference types="vite/client" />

declare global {
  interface Window {
    electronAPI?: {
      backendPort?: string;
    };
  }
}

export {};
