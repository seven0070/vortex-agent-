import { contextBridge } from 'electron';
import { BACKEND_PORT } from './constants';

contextBridge.exposeInMainWorld('electronAPI', {
  backendPort: BACKEND_PORT,
});
