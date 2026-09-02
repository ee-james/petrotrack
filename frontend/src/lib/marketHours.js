/**
 * marketHours.js - Market open/closed status per commodity code.
 *
 * Schedule types:
 *   'f245'  - CME/NYMEX/ICE Futures: Sun 18:00 - Fri 17:00 ET,
 *             with a daily maintenance break 17:00-18:00 ET (Mon-Thu)
 *   null    - No schedule (count/weekly data, OTC posted prices, etc.)
 */

// ---- Per-code schedule assignments ----
const F245 = 'f245';

const SCHEDULE = {
  // Crude oils
  WTI_USD:             F245, BRENT_USD:          F245, BRENT_CRUDE_USD:     F245,
  DUBAI_CRUDE_USD:     F245, URALS_CRUDE_USD:    F245, WCS_CRUDE_USD:       F245,
  MARS_USD:            F245, LOUISIANA_LIGHT_USD: F245, ANS_WEST_COAST_USD: F245,
  BASRAH_MEDIUM_USD:   F245, BASRAH_HEAVY_USD:   F245, TAPIS_CRUDE_USD:     F245,

  // Natural gas
  NATURAL_GAS_USD:           F245, NATURAL_GAS_GBP:       F245,
  NATURAL_GAS_WAHA:          F245, DUTCH_TTF_EUR:          F245,
  DUTCH_TTF_NATURAL_GAS_USD: F245, JKM_LNG_USD:            F245,

  // Refined products (exchange-traded)
  GASOLINE_USD:              F245, GASOLINE_RBOB_USD:       F245,
  HEATING_OIL_USD:           F245, ULSD_DIESEL_USD:         F245,
  DIESEL_USD:                F245, ETHANOL_USD:             F245,
  PROPANE_MONT_BELVIEU_USD:  F245,
  MGO_05S_USD:               F245, VLSFO_USD:               F245,
  HFO_380_USD:               F245, HFO_180_USD:             F245,

  // Coal futures
  CME_COAL_USD:              F245, CAPP_COAL_USD:           F245,
  PRB_COAL_USD:              F245, ILLINOIS_COAL_USD:       F245,
  NEWCASTLE_COAL_USD:        F245, NYMEX_APPALACHIAN_USD:   F245,
  NYMEX_WESTERN_RAIL_USD:    F245,

  // Carbon / emissions
  EU_CARBON_EUR:             F245, UK_CARBON_GBP:           F245,
  EU_CARBON_FUTURES:         F245, CARBON_EMISSIONS_USD:    F245,

  // Currencies
  EUR_USD:                   F245, GBP_USD:                 F245,
  USD_NOK:                   F245, EUR_NOK:                 F245,

  // Metals
  GOLD_USD:                  F245,

  // Futures contracts
  BRENT_FUTURES:             F245, WTI_FUTURES:             F245,
  NATGAS_FUTURES:            F245, GASOIL_FUTURES:          F245,
  BRENT_FUTURES_CONTINUOUS:  F245, WTI_FUTURES_CONTINUOUS:  F245,

  // Everything else (retail diesel, jet fuel, coal spot, OPEC basket,
  // uranium, storage, rig counts, frac spreads, permits, DUC, drilled,
  // completed, annual contracts) → null (no market hours shown)
};

// ---- Helpers ----

/** Convert a UTC Date to Eastern Time components. */
function toET(date) {
  // toLocaleString returns ET wall-clock time as a string;
  // wrapping in new Date() gives us a Date whose .getDay() / .getHours() etc.
  // reflect ET (treating it as local - a well-known JS timezone hack).
  return new Date(date.toLocaleString('en-US', { timeZone: 'America/New_York' }));
}

function formatDuration(ms) {
  const totalMin = Math.ceil(ms / 60_000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}

// ---- Core logic ----

function f245Status(now) {
  const et  = toET(now);
  const day = et.getDay();                           // 0=Sun … 6=Sat
  const t   = et.getHours() + et.getMinutes() / 60; // decimal hours in ET

  // Determine open/closed
  let open;
  if      (day === 6)             open = false;          // Saturday
  else if (day === 0)             open = t >= 18;        // Sunday: opens 18:00
  else if (day === 5)             open = t < 17;         // Friday: closes 17:00
  else /* Mon-Thu */              open = !(t >= 17 && t < 18); // daily break 17-18

  if (open) return { open: true };

  // Compute hours until next open
  let h;
  if      (day === 6)             h = (24 - t) + 18;           // → Sun 18:00
  else if (day === 5 && t >= 17)  h = (24 - t) + 24 + 18;     // → Sun 18:00 (+Sat)
  else if (day === 0 && t < 18)   h = 18 - t;                   // → today 18:00
  else /* daily break */          h = 18 - t;                   // → today 18:00

  return { open: false, opensIn: formatDuration(h * 3_600_000) };
}

// ---- Public API ----

/**
 * Returns null (no schedule) or { open: boolean, opensIn?: string }.
 * opensIn is a human-readable string like "2h 30m" when open === false.
 */
export function getMarketStatus(code) {
  const schedule = SCHEDULE[code] ?? null;
  if (!schedule) return null;
  if (schedule === 'f245') return f245Status(new Date());
  return null;
}
