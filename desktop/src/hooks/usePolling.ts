import { useEffect, useRef } from 'react';

export function usePolling(fn: () => Promise<void> | void, intervalMs: number, enabled = true) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled) return;
    void fnRef.current();
    const id = window.setInterval(() => void fnRef.current(), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs, enabled]);
}
