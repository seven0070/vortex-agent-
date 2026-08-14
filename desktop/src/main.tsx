import React from 'react';
import { createRoot } from 'react-dom/client';
import { AppProvider } from './stores/AppStore';
import { App } from './app/App';
import './styles/global.css';

createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppProvider>
      <App />
    </AppProvider>
  </React.StrictMode>,
);
