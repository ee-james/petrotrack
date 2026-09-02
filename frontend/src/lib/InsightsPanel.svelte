<script>
  import { onMount, onDestroy } from 'svelte';
  import { getMeta } from './commodityMeta.js';

  export let metricsCache = {};
  export let codes        = [];

  const COUNT_PATTERN = /RIG_COUNT|FRAC_SPREAD|WELL_PERMIT|DUC_WELL|WELLS_DRILLED|WELLS_COMPLETED|_STORAGE|SPREAD_COUNT/;

  $: priceCodes  = codes.filter(c => !COUNT_PATTERN.test(c));
  $: withMetrics = priceCodes
    .map(c => ({ code: c, m: metricsCache[c] }))
    .filter(({ m }) => m && m.pct_change != null);

  $: sorted  = [...withMetrics].sort((a, b) => (b.m.pct_change ?? 0) - (a.m.pct_change ?? 0));
  $: gainers = sorted.filter(({ m }) => m.pct_change > 0).slice(0, 6);
  $: losers  = [...sorted].reverse().filter(({ m }) => m.pct_change < 0).slice(0, 6);
  $: alerts  = withMetrics.filter(({ m }) => m.alert);

  // ---- Market hours ----
  // All schedules expressed in US Eastern time (ET).

  let now = new Date();
  let ticker;

  onMount(()  => { ticker = setInterval(() => { now = new Date(); }, 30_000); });
  onDestroy(() => clearInterval(ticker));

  function nyParts(date) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      weekday: 'short', hour: 'numeric', minute: '2-digit', hour12: false,
    }).formatToParts(date);
    const get = t => parts.find(p => p.type === t)?.value ?? '0';
    const h = parseInt(get('hour'));
    const m = parseInt(get('minute'));
    return { wd: get('weekday'), h, m, t: h * 60 + m };
  }

  function fmtNY(date) {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      weekday: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
    }).format(date);
  }

  function fmtLondon(date) {
    return new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Europe/London',
      hour: 'numeric', minute: '2-digit', hour12: false,
    }).format(date);
  }

  // CME Globex Energy & Metals (WTI, NatGas, Gasoline, Heating Oil, Gold)
  // Sun 18:00 ET -> Fri 17:00 ET; daily maintenance break 17:00-18:00 ET
  function isCMEOpen({ wd, t }) {
    if (wd === 'Sat') return false;
    if (wd === 'Sun') return t >= 18 * 60;
    if (wd === 'Fri') return t < 17 * 60;
    return !(t >= 17 * 60 && t < 18 * 60);
  }

  // ICE Futures Europe (Brent Crude, Gasoil, EU/UK Carbon)
  // Opens later Sunday; Mon-Thu break 17:00-19:00 ET
  function isICEOpen({ wd, t }) {
    if (wd === 'Sat') return false;
    if (wd === 'Sun') return t >= 20 * 60;
    if (wd === 'Fri') return t < 17 * 60;
    return !(t >= 17 * 60 && t < 19 * 60);
  }

  // Forex OTC (EUR/USD, GBP/USD, USD/NOK, EUR/NOK)
  // Sun 17:00 ET -> Fri 17:00 ET, continuous
  function isForexOpen({ wd, t }) {
    if (wd === 'Sat') return false;
    if (wd === 'Sun') return t >= 17 * 60;
    if (wd === 'Fri') return t < 17 * 60;
    return true;
  }

  // OTC Coal & LNG reference prices - business hours only
  // Mon-Fri 08:00-17:00 ET
  function isOTCOpen({ wd, t }) {
    if (wd === 'Sat' || wd === 'Sun') return false;
    return t >= 8 * 60 && t < 17 * 60;
  }

  $: ny       = nyParts(now);
  $: nyStr     = fmtNY(now);
  $: londonStr = fmtLondon(now);

  $: exchanges = [
    { name: 'CME / NYMEX',  products: 'WTI · NatGas · Gasoline · HO · Gold', open: isCMEOpen(ny),  hours: 'Sun 6 PM - Fri 5 PM ET'  },
    { name: 'ICE Futures',  products: 'Brent · Gasoil · EU/UK Carbon',        open: isICEOpen(ny),  hours: 'Sun 8 PM - Fri 5 PM ET'  },
    { name: 'Forex OTC',    products: 'EUR/USD · GBP/USD · NOK pairs',         open: isForexOpen(ny), hours: 'Sun 5 PM - Fri 5 PM ET' },
    { name: 'Coal/LNG OTC', products: 'Newcastle · CAPP · JKM LNG',           open: isOTCOpen(ny),  hours: 'Mon-Fri 8 AM - 5 PM ET'  },
  ];

  function fmtPct(v) {
    const sign = v > 0 ? '+' : '';
    return `${sign}${v.toFixed(2)}%`;
  }
</script>

<aside class="insights">

  <!-- Market Hours -->
  <section class="widget">
    <h2 class="widget-title">Market Hours</h2>
    <div class="clock-row">
      <span class="clock-item">
        <span class="clock-label">New York</span>
        <span class="clock-time">{nyStr}</span>
      </span>
      <span class="clock-item">
        <span class="clock-label">London</span>
        <span class="clock-time">{londonStr}</span>
      </span>
    </div>
    <div class="exchange-list">
      {#each exchanges as ex}
        <div class="exchange-row">
          <span class="ex-dot" class:open={ex.open} class:closed={!ex.open}></span>
          <span class="ex-name">{ex.name}</span>
          <span class="ex-status" class:open={ex.open} class:closed={!ex.open}>{ex.open ? 'OPEN' : 'CLOSED'}</span>
        </div>
        <div class="ex-products">{ex.products}</div>
      {/each}
    </div>
  </section>

  <!-- Top Movers -->
  {#if gainers.length || losers.length}
    <section class="widget">
      <h2 class="widget-title">Top Movers</h2>
      {#if gainers.length}
        <div class="mover-group-label up">Gainers</div>
        {#each gainers as { code, m }}
          <div class="mover-row">
            <span class="mover-flag">{getMeta(code).flag ?? ''}</span>
            <span class="mover-name">{getMeta(code).name}</span>
            <span class="mover-pct up">{fmtPct(m.pct_change)}</span>
          </div>
        {/each}
      {/if}
      {#if losers.length}
        <div class="mover-group-label down">Losers</div>
        {#each losers as { code, m }}
          <div class="mover-row">
            <span class="mover-flag">{getMeta(code).flag ?? ''}</span>
            <span class="mover-name">{getMeta(code).name}</span>
            <span class="mover-pct down">{fmtPct(m.pct_change)}</span>
          </div>
        {/each}
      {/if}
    </section>
  {/if}

  <!-- Active Alerts -->
  <section class="widget" class:widget-alerts={alerts.length > 0} class:quiet={alerts.length === 0}>
    <h2 class="widget-title">
      Alerts
      {#if alerts.length}<span class="alert-badge">{alerts.length}</span>{/if}
    </h2>
    {#if alerts.length}
      {#each alerts as { code, m }}
        <div class="alert-row">
          <span class="mover-flag">{getMeta(code).flag ?? ''}</span>
          <span class="mover-name">{getMeta(code).name}</span>
          <span class="mover-pct" class:up={m.pct_change > 0} class:down={m.pct_change < 0}>
            {fmtPct(m.pct_change)}
          </span>
        </div>
      {/each}
    {:else}
      <p class="quiet-msg">No active alerts</p>
    {/if}
  </section>

</aside>

<style>
  .insights {
    display:        flex;
    flex-direction: column;
    gap:            10px;
    overflow-y:     auto;
    min-height:     0;
    padding:        4px 0 4px 0;
  }

  .widget {
    background:    color-mix(in srgb, var(--color-neon) 3%, var(--color-background));
    border:        1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
    border-radius: var(--tile-corner-radius);
    padding:       12px 14px;
    flex-shrink:   0;
  }

  .widget.quiet { opacity: 0.4; }

  .widget-title {
    font-size:      0.63rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color:          var(--color-neon);
    opacity:        0.75;
    margin:         0 0 10px;
    display:        flex;
    align-items:    center;
    gap:            6px;
  }

  .alert-badge {
    background:    var(--color-alert);
    border-radius: 10px;
    color:         #eee;
    font-size:     0.6rem;
    padding:       1px 6px;
    opacity:       1;
    letter-spacing: 0;
  }

  /* Clock */
  .clock-row {
    display:       flex;
    gap:           20px;
    margin-bottom: 12px;
  }

  .clock-item {
    display:        flex;
    flex-direction: column;
    gap:            2px;
  }

  .clock-label {
    font-size:      0.57rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color:          var(--color-text-secondary);
  }

  .clock-time {
    font-size:            0.85rem;
    color:                var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }

  /* Exchange rows */
  .exchange-list  { display: flex; flex-direction: column; gap: 2px; }

  .exchange-row {
    display:     flex;
    align-items: center;
    gap:         7px;
    margin-top:  4px;
  }

  .ex-dot {
    width:         7px;
    height:        7px;
    border-radius: 50%;
    flex-shrink:   0;
  }
  .ex-dot.open   { background: var(--color-price-up); box-shadow: 0 0 5px var(--color-price-up); }
  .ex-dot.closed { background: var(--color-text-secondary); opacity: 0.35; }

  .ex-name {
    flex:      1;
    font-size: 0.72rem;
    color:     var(--color-text-primary);
  }

  .ex-status {
    font-size:      0.6rem;
    letter-spacing: 0.08em;
    font-weight:    600;
  }
  .ex-status.open   { color: var(--color-price-up); }
  .ex-status.closed { color: var(--color-text-secondary); opacity: 0.45; }

  .ex-products {
    font-size: 0.58rem;
    color:     var(--color-text-secondary);
    padding:   1px 0 4px 14px;
    opacity:   0.65;
  }

  /* Movers */
  .mover-group-label {
    font-size:      0.58rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin:         6px 0 2px;
    opacity:        0.7;
  }
  .mover-group-label.up   { color: var(--color-price-up); }
  .mover-group-label.down { color: var(--color-price-down); }

  .mover-row, .alert-row {
    display:     flex;
    align-items: center;
    gap:         6px;
    padding:     2px 0;
  }

  .mover-flag { font-size: 0.8rem; width: 1.4em; text-align: center; flex-shrink: 0; }

  .mover-name {
    flex:          1;
    font-size:     0.72rem;
    color:         var(--color-text-primary);
    white-space:   nowrap;
    overflow:      hidden;
    text-overflow: ellipsis;
  }

  .mover-pct {
    font-size:            0.72rem;
    font-variant-numeric: tabular-nums;
    font-weight:          600;
    flex-shrink:          0;
  }
  .mover-pct.up   { color: var(--color-price-up); }
  .mover-pct.down { color: var(--color-price-down); }

  .quiet-msg { font-size: 0.7rem; color: var(--color-text-secondary); margin: 0; }
</style>
