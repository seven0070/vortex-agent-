import { useAppStore } from '../stores/AppStore';

export function TopBar() {
  const { online, backendRunning, theme, toggleTheme } = useAppStore();
  return (
    <header className="topbar">
      <div className="brand">VORTEX</div>
      <div className="topbar-right">
        <span className={`status-dot ${online ? 'online' : 'offline'}`}>{online ? '● ONLINE' : '● OFFLINE'}</span>
        <span className={`status-chip ${backendRunning ? 'ok' : ''}`}>{backendRunning ? 'Backend Running' : 'Backend Stopped'}</span>
        <button type="button" className="ghost-button" onClick={toggleTheme}>
          Theme: {theme}
        </button>
      </div>
    </header>
  );
}
