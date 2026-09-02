const { contextBridge, ipcRenderer } = require('electron');
const path = require('path');
const fs   = require('fs');

// Read backend URL from config.json next to this file
let apiBase = 'http://localhost:8000';
try {
  const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
  if (cfg.backendUrl) apiBase = cfg.backendUrl.replace(/\/$/, '');
} catch { /* use default */ }

contextBridge.exposeInMainWorld('__ELECTRON__', {
  isElectron: true,
  apiBase,
});
