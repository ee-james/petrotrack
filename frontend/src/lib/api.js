// In Electron, API calls must be absolute (no nginx proxy).
// window.__ELECTRON__.apiBase is set by preload.js from electron/config.json.
const BASE = (typeof window !== 'undefined' && window.__ELECTRON__?.apiBase) ?? '';

async function apiFetch(url, options = {}) {
  url = BASE + url;
  const res = await fetch(url, options);
  if (!res.ok) {
    let status = null;
    try { const body = await res.json(); status = body?.detail?.status ?? null; } catch {}
    const err = new Error(`${res.status} ${res.statusText} - ${url}`);
    err.apiStatus = status;
    throw err;
  }
  return res.json();
}

export const getConfig   = ()           => apiFetch('/config');
export const getMetrics  = (code)       => apiFetch(`/metrics/${code}`);
export const getPrices   = (code)       => apiFetch(`/prices/${code}`);
export const getSettings = (code)       => apiFetch(`/settings/${code}`);

export const putSettings = (code, alert_threshold) =>
  apiFetch(`/settings/${code}`, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ alert_threshold }),
  });

export const getAvailableCommodities  = () => apiFetch('/commodities/available');
export const getCommoditiesCatalog  = () => apiFetch('/commodities/catalog');
export const getPlanCheck             = () => apiFetch('/commodities/plan-check');

export const putEnabledCommodities = (enabled) =>
  apiFetch('/commodities/enabled', {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ enabled }),
  });

export const getLastRefresh = () => apiFetch('/last_refresh');

export const putTheme = (theme) =>
  apiFetch('/config/theme', {
    method:  'PUT',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(theme),
  });
