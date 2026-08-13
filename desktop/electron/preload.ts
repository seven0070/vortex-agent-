import { contextBridge } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  backendPort: '8000',
});
