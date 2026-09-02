<script>
  import { createEventDispatcher, onMount, afterUpdate } from 'svelte';
  import { getMetrics, getPrices } from './api.js';
  import { getMeta }               from './commodityMeta.js';
  import { getMarketStatus }       from './marketHours.js';
  import { playAlertBeep }         from './audio.js';
  import SparkLine    from './SparkLine.svelte';
  import RollingPrice from './RollingPrice.svelte';
  import Flag         from './Flag.svelte';

  export let code;
  export let refreshKey   = 0;
  export let isDuplicate  = false;

  const dispatch = createEventDispatcher();

  let metrics    = null;
  let prices     = [];
  let error      = null;
  let errorStatus = null;
  let prevAlert  = null;

  const { cc, flag, name, desc } = getMeta(code);

  // ---- Touch detection (for tooltip cta text) ----
  let isTouch = false;
  let tooltipVisible = false;

  // ---- Tooltip positioning ----
  let tooltipEl;
  let nameEl;

  function showTooltip() { if (desc) tooltipVisible = true; }
  function hideTooltip() { tooltipVisible = false; }

  // ---- Overflow-scroll detection ----
  let nameOuter;
  let nameInner;
  let overflowPx = 0;

  function checkOverflow() {
    if (nameOuter && nameInner) {
      overflowPx = Math.max(0, nameInner.scrollWidth - nameOuter.clientWidth);
    }
  }
  onMount(() => {
    checkOverflow();
    isTouch = navigator.maxTouchPoints > 0 || window.matchMedia('(pointer:coarse)').matches;
  });
  afterUpdate(checkOverflow);

  // ---- Data loading ----
  const STATUS_MESSAGES = {
    not_on_plan: 'Not included in your API subscription',
    no_data:     'No price data received from provider',
    api_error:   'Provider API returned an error',
  };

  async function loadAll() {
    error = null;
    errorStatus = null;
    try {
      const [m, p] = await Promise.all([getMetrics(code), getPrices(code)]);

      if (prevAlert === false && m.alert === true) {
        playAlertBeep();
      }
      prevAlert = m.alert;

      metrics = m;
      prices  = p.prices;
      dispatch('metrics', { code, metrics: m });
    } catch (e) {
      error       = e.message;
      errorStatus = e.apiStatus ?? null;
      dispatch('metrics', { code, metrics: null, errorStatus });
    }
  }

  $: if (refreshKey !== undefined) { loadAll(); }

  let now = Date.now();
  onMount(() => {
    const id = setInterval(() => { now = Date.now(); }, 30_000);
    return () => clearInterval(id);
  });

  // Recompute market status every minute
  let marketStatus = getMarketStatus(code);
  onMount(() => {
    const id = setInterval(() => { marketStatus = getMarketStatus(code); }, 60_000);
    return () => clearInterval(id);
  });

  function fmt(v, d = 2) {
    if (v === null || v === undefined) return null;
    return Number(v).toFixed(d);
  }

  function timeAgo(iso, _now) {
    if (!iso) return '';
    const s = Math.floor((_now - new Date(iso).getTime()) / 1000);
    if (s < 60)    return `${s}s ago`;
    if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }

  function onClick() { dispatch('select', { code }); }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="row"
  class:alert={metrics && metrics.alert}
  class:dup={isDuplicate}
  on:click={onClick}
  role="button"
  tabindex="0"
>
  <!-- Flag -->
  <span class="flag"><Flag {cc} {flag} {name} /></span>

  <!-- Alert column -->
  <span class="alert-tag" class:active={metrics?.alert}>!</span>

  <!-- Name (dynamic width, overflow marquee on hover, tooltip on hover) -->
  <span
    class="name-outer"
    bind:this={nameOuter}
    on:mouseenter={showTooltip}
    on:mouseleave={hideTooltip}
  >
    <span
      class="name-inner"
      class:scrolling={overflowPx > 0}
      style={overflowPx > 0 ? `--overflow-px: ${overflowPx}px` : ''}
      bind:this={nameInner}
    ><a
      class="name-link"
      href="https://www.google.com/search?q={encodeURIComponent(name + ' commodity information')}"
      target="_blank"
      rel="noopener"
      on:click|stopPropagation
    >{name}</a></span>

    {#if tooltipVisible && desc}
      <div class="name-tooltip" bind:this={tooltipEl}>
        <p>{desc}</p>
        <span class="tooltip-cta">{isTouch ? 'Tap' : 'Click'} for more →</span>
      </div>
    {/if}
  </span>

  {#if error}
    <span class="unavailable">{STATUS_MESSAGES[errorStatus] ?? 'Data temporarily unavailable'}</span>

  {:else if !metrics}
    <span class="loading">…</span>

  {:else if metrics.is_count}
    <!-- count-type display (rigs, permits, wells) -->
    <span class="price" class:up={!metrics.count_change || metrics.count_change >= 0} class:down={metrics.count_change !== null && metrics.count_change < 0}>
      <RollingPrice value={String(Math.round(metrics.price))} />
    </span>

    {#if metrics.count_change !== null}
      <span class="pct" class:up={metrics.count_change >= 0} class:down={metrics.count_change < 0}>
        {metrics.count_change >= 0 ? '+' : ''}{metrics.count_change}
      </span>
    {:else}
      <span class="no-data">-</span>
    {/if}

    <span class="age" style="margin-left: auto;">{timeAgo(metrics.fetched_at, now)}</span>

    <span class="spark">
      <SparkLine {prices} h={22} />
    </span>

    {#if isDuplicate}
      <span class="dup-label">already featured</span>
    {/if}

  {:else}
    <!-- price-type display -->
    <span
      class="price"
      class:up={metrics.pct_change === null || metrics.pct_change >= 0}
      class:down={metrics.pct_change !== null && metrics.pct_change < 0}
    >
      <RollingPrice value={fmt(metrics.price)} />
      <span class="price-currency">{metrics.currency}</span>
    </span>

    <!-- pct change -->
    {#if metrics.pct_change !== null}
      <span
        class="pct"
        class:up={metrics.pct_change >= 0}
        class:down={metrics.pct_change < 0}
      >{metrics.pct_change >= 0 ? '+' : ''}{fmt(metrics.pct_change)}%</span>
    {:else}
      <span class="no-data">NO DATA</span>
    {/if}

    <!-- 30d H/L -->
    <span class="hl-block">
      <span class="hl-label">30d</span>
      {#if metrics.high_30d !== null && metrics.low_30d !== null}
        <span class="hl-val">{fmt(metrics.high_30d)}&thinsp;/&thinsp;{fmt(metrics.low_30d)}</span>
      {:else}
        <span class="no-data">NO DATA</span>
      {/if}
    </span>

    <!-- 24h H/L -->
    <span class="hl-block">
      <span class="hl-label">24h</span>
      {#if metrics.high_24h !== null && metrics.low_24h !== null}
        <span class="hl-val">{fmt(metrics.high_24h)}&thinsp;/&thinsp;{fmt(metrics.low_24h)}</span>
      {:else}
        <span class="no-data">NO DATA</span>
      {/if}
    </span>

    <!-- last update age -->
    <span class="age">{timeAgo(metrics.fetched_at, now)}</span>

    <!-- market closed indicator -->
    {#if marketStatus && !marketStatus.open}
      <span class="market-closed" title="Market is currently closed">
        opens {marketStatus.opensIn}
      </span>
    {/if}

    <!-- mini sparkline -->
    <span class="spark">
      <SparkLine {prices} h={22} />
    </span>

    {#if isDuplicate}
      <span class="dup-label">already featured</span>
    {/if}
  {/if}
</div>

<style>
  .row {
    display:       flex;
    align-items:   center;
    flex-wrap:     nowrap;
    gap:           8px;
    padding:       4px 10px;
    cursor:        pointer;
    border-bottom: 1px solid color-mix(in srgb, var(--color-neon) 9%, transparent);
    transition:    background var(--animation-duration);
    font-size:     0.76rem;
    overflow:      hidden;
  }
  .row:last-child  { border-bottom: none; }
  .row:hover       { background: color-mix(in srgb, var(--color-neon) 5%, var(--color-background)); }
  .row.alert       { background: color-mix(in srgb, var(--color-alert) 5%, var(--color-background)); }
  .row.dup         { animation: dup-flash 0.75s ease; }

  @keyframes dup-flash {
    0%, 100% { background: transparent; }
    30%, 70% { background: color-mix(in srgb, var(--color-alert) 12%, var(--color-background)); }
  }

  /* ---- Flag column ---- */
  .flag {
    flex-shrink: 0;
    font-size:   0.9rem;
    width:       22px;
    text-align:  center;
    line-height: 1;
  }

  /* ---- Name column (dynamic width via CSS var set on parent section) ---- */
  .name-outer {
    width:       var(--code-col-w, 140px);
    flex-shrink: 0;
    overflow:    hidden;
    position:    relative;
  }

  .name-inner {
    display:     inline-block;
    white-space: nowrap;
    color:          var(--color-text-secondary);
    letter-spacing: 0.03em;
    font-size:      0.71rem;
  }

  .name-link {
    color:           inherit;
    text-decoration: none;
    cursor:          pointer;
  }
  .name-link:hover { color: var(--color-neon); }

  /* Marquee on hover when text overflows */
  .row:hover .name-inner.scrolling {
    animation: name-scroll 3.5s ease-in-out infinite;
  }
  @keyframes name-scroll {
    0%,  15% { transform: translateX(0); }
    50%, 65% { transform: translateX(calc(-1 * var(--overflow-px, 0px))); }
    100%     { transform: translateX(0); }
  }

  /* Right-edge fade hint when text overflows (static) */
  .name-outer::after {
    content:    '';
    position:   absolute;
    right:      0;
    top:        0;
    height:     100%;
    width:      16px;
    background: linear-gradient(to right, transparent, var(--color-background));
    pointer-events: none;
    opacity:    0;
    transition: opacity var(--animation-duration);
  }
  .name-outer:has(.scrolling)::after { opacity: 1; }

  /* ---- Tooltip ---- */
  .name-tooltip {
    position:      absolute;
    left:          0;
    top:           calc(100% + 6px);
    z-index:       100;
    width:         240px;
    padding:       10px 12px;
    background:    color-mix(in srgb, var(--color-neon) 6%, var(--color-background));
    border:        1px solid color-mix(in srgb, var(--color-neon) 30%, transparent);
    border-radius: 4px;
    box-shadow:    0 4px 18px rgba(0,0,0,0.55);
    pointer-events: none;
  }
  .name-tooltip p {
    margin:         0 0 6px;
    font-size:      0.68rem;
    line-height:    1.45;
    color:          var(--color-text-primary);
    white-space:    normal;
    letter-spacing: 0.01em;
  }
  .tooltip-cta {
    font-size:      0.62rem;
    color:          var(--color-neon);
    opacity:        0.75;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* ---- Alert tag - always in flow to preserve column alignment ---- */
  .alert-tag {
    flex-shrink:    0;
    width:          18px;
    text-align:     center;
    font-size:      0.58rem;
    font-weight:    bold;
    padding:        1px 3px;
    border-radius:  2px;
    background:     var(--color-alert);
    color:          #fff;
    letter-spacing: 0.04em;
    line-height:    1.5;
    visibility:     hidden;
  }
  .alert-tag.active { visibility: visible; }

  /* ---- Price ---- */
  .price {
    display:     inline-flex;
    align-items: baseline;
    gap:         3px;
    width:       100px;
    flex-shrink: 0;
    font-weight: bold;
    color:       var(--color-text-primary);
    transition:  color var(--animation-duration);
  }
  .price.up   { color: var(--color-price-up); }
  .price.down { color: var(--color-price-down); }

  .price-currency {
    font-size:      0.65rem;
    font-weight:    normal;
    opacity:        0.6;
    align-self:     flex-end;
    padding-bottom: 0.05em;
  }

  /* ---- Pct change ---- */
  .pct {
    width:                52px;
    flex-shrink:          0;
    font-variant-numeric: tabular-nums;
  }
  .pct.up   { color: var(--color-price-up); }
  .pct.down { color: var(--color-price-down); }

  /* ---- H/L blocks ---- */
  .hl-block {
    display:              flex;
    gap:                  4px;
    align-items:          center;
    font-size:            0.69rem;
    font-variant-numeric: tabular-nums;
    flex-shrink:          0;
  }
  .hl-label { color: var(--color-text-secondary); }
  .hl-val   { color: var(--color-text-primary); }

  /* ---- Misc ---- */
  .no-data {
    font-size:      0.62rem;
    font-weight:    300;
    color:          var(--color-text-secondary);
    opacity:        0.55;
    letter-spacing: 0.04em;
  }

  .age {
    flex-shrink:          0;
    font-size:            0.69rem;
    font-variant-numeric: tabular-nums;
    color:                var(--color-text-secondary);
  }

  .spark {
    width:       72px;
    flex-shrink: 0;
    opacity:     0.7;
    margin-left: auto;
  }

  .dup-label {
    font-size:   0.62rem;
    color:       var(--color-alert);
    flex-shrink: 0;
  }

  .market-closed {
    flex-shrink:    0;
    font-size:      0.60rem;
    color:          var(--color-text-secondary);
    opacity:        0.6;
    letter-spacing: 0.03em;
    white-space:    nowrap;
  }

  .loading     { color: var(--color-text-secondary); font-size: 0.72rem; }
  .unavailable { color: var(--color-text-secondary); font-size: 0.68rem; opacity: 0.45; font-style: italic; }
</style>
