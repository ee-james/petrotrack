<script>
  import { onMount, onDestroy } from 'svelte';
  import { getMetrics, getPrices, getSettings, putSettings } from './api.js';
  import { startAlertLoop, stopAlertLoop } from './audio.js';
  import { getMarketStatus } from './marketHours.js';
  import SparkLine      from './SparkLine.svelte';
  import RollingPrice   from './RollingPrice.svelte';

  export let code;
  export let refreshKey = 0;

  let metrics   = null;
  let prices    = [];
  let threshold = null;
  let error     = null;
  let loading   = true;

  let priceDirection = null;  // 'up' | 'down' | null
  let prevPrice      = null;
  let acknowledged   = false; // user dismissed the glow; badge stays until condition clears
  let isFirstLoad    = true;  // distinguishes page-load from in-session alert transitions

  const ackKey = () => `ack_${code}`;

  function loadAck(fetchedAt) {
    return sessionStorage.getItem(ackKey()) === fetchedAt;
  }

  function saveAck(fetchedAt) {
    sessionStorage.setItem(ackKey(), fetchedAt);
  }

  function clearAck() {
    sessionStorage.removeItem(ackKey());
  }

  let editingThreshold = false;
  let editValue        = '';

  async function loadAll() {
    loading = true;
    error   = null;
    try {
      const [m, p, s] = await Promise.all([
        getMetrics(code),
        getPrices(code),
        getSettings(code),
      ]);

      // Flash price direction on change
      if (prevPrice !== null && m.price !== prevPrice) {
        priceDirection = m.price > prevPrice ? 'up' : 'down';
        setTimeout(() => { priceDirection = null; }, 600);
      }
      prevPrice = m.price;

      const wasAlert = metrics?.alert ?? false;
      metrics   = m;
      prices    = p.prices;
      threshold = s.alert_threshold;

      // On first page load, always restore from sessionStorage if alert is active.
      // On subsequent loads within the session, clear ack only on a genuine
      // false→true transition (new alert) or when the condition clears.
      if (!m.alert) {
        clearAck(); acknowledged = false;
        stopAlertLoop(code);
      } else if (!isFirstLoad && !wasAlert) {
        clearAck(); acknowledged = false;  // new alert fired this session
        startAlertLoop(code);
      } else {
        acknowledged = loadAck(m.fetched_at);
        if (!acknowledged) startAlertLoop(code);
        else stopAlertLoop(code);
      }
      isFirstLoad = false;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function acknowledgeAlert() {
    acknowledged = true;
    stopAlertLoop(code);
    if (metrics?.fetched_at) saveAck(metrics.fetched_at);
  }

  onDestroy(() => stopAlertLoop(code));

  // React to refreshKey from App (auto/manual refresh) and also on first mount
  $: if (refreshKey !== undefined) { loadAll(); }

  // Ticker so timeAgo re-evaluates without waiting for a full data refresh
  let now = Date.now();
  onMount(() => {
    const id = setInterval(() => { now = Date.now(); }, 30_000);
    return () => clearInterval(id);
  });

  let marketStatus = getMarketStatus(code);
  onMount(() => {
    const id = setInterval(() => { marketStatus = getMarketStatus(code); }, 60_000);
    return () => clearInterval(id);
  });

  // --- Threshold editor ---
  function startEdit() {
    editValue        = threshold !== null ? String(threshold) : '';
    editingThreshold = true;
  }

  function cancelEdit() {
    editingThreshold = false;
  }

  async function saveThreshold() {
    const val = parseFloat(editValue);
    if (!isNaN(val) && val >= 0) {
      try {
        await putSettings(code, val);
      } catch (e) {
        console.error('Failed to save threshold', e);
      }
    }
    editingThreshold = false;
    await loadAll();
  }

  function onKeydown(e) {
    if (e.key === 'Enter')  saveThreshold();
    if (e.key === 'Escape') cancelEdit();
  }

  // --- Formatting ---
  function fmt(v, digits = 2) {
    if (v === null || v === undefined) return null;
    return Number(v).toFixed(digits);
  }

  function fmtTime(iso) {
    if (!iso) return '';
    const d   = new Date(iso);
    const now = new Date();
    const sameDay = d.toISOString().slice(0, 10) === now.toISOString().slice(0, 10);
    return sameDay
      ? d.toISOString().slice(11, 16) + 'Z'
      : d.toISOString().slice(0, 16).replace('T', ' ') + 'Z';
  }

  function timeAgo(iso, _now) {
    if (!iso) return '';
    const s = Math.floor((_now - new Date(iso).getTime()) / 1000);
    if (s < 60)    return `${s}s ago`;
    if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }
</script>

<div class="tile" class:alert={metrics && metrics.alert && !acknowledged}>
  <div class="tile-header">
    <span class="code">{code.replace(/_USD$/, '')}</span>
    {#if metrics && metrics.alert}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <button
        class="alert-badge"
        class:acknowledged
        on:click|stopPropagation={acknowledgeAlert}
        title={acknowledged ? 'Glow silenced - condition still active' : 'Click to silence glow'}
      >ALERT</button>
    {/if}
  </div>

  {#if loading && !metrics}
    <div class="placeholder">Loading…</div>

  {:else if error}
    <div class="tile-unavailable">&lt;not available&gt;</div>

  {:else if metrics}
    <div class="tile-body">
      <div class="tile-info">
        <!-- Price + % change -->
        <div class="price-row">
          <span
            class="price-value"
            class:up={priceDirection === 'up'}
            class:down={priceDirection === 'down'}
          >
            {#if metrics.is_count}
              <RollingPrice value={String(Math.round(metrics.price))} />
            {:else}
              <RollingPrice value={fmt(metrics.price)} />
              <span class="price-currency">{metrics.currency}</span>
            {/if}
          </span>
          {#if metrics.is_count && metrics.count_change !== null}
            <span
              class="pct-change"
              class:up={metrics.count_change >= 0}
              class:down={metrics.count_change < 0}
            >
              {metrics.count_change >= 0 ? '+' : ''}{metrics.count_change}
            </span>
          {:else if !metrics.is_count && metrics.pct_change !== null}
            <span
              class="pct-change"
              class:up={metrics.pct_change >= 0}
              class:down={metrics.pct_change < 0}
            >
              {metrics.pct_change >= 0 ? '+' : ''}{fmt(metrics.pct_change)}%
            </span>
          {/if}
        </div>

        <!-- Day-open price (fades after tile enters) -->
        {#if metrics.open_price !== null}
          <div class="open-row">
            <span class="open-label">open</span>
            <span class="open-value">{fmt(metrics.open_price)} {metrics.currency}</span>
          </div>
        {/if}

        <!-- Last update age -->
        <div class="last-update">
          <span class="last-label">Last update</span>
          <span class="last-age">{timeAgo(metrics.fetched_at, now)}</span>
        </div>

        <!-- Market hours -->
        {#if marketStatus && !marketStatus.open}
          <div class="market-closed">
            Market opens in {marketStatus.opensIn}
          </div>
        {/if}

        <!-- Previous price -->
        {#if metrics.price_previous !== null}
          <div class="prev-row">
            <span class="prev-label">24h ref</span>
            <span class="prev-value">{fmt(metrics.price_previous)} {metrics.currency}</span>
            <span class="prev-time">@ {fmtTime(metrics.fetched_at_previous)}</span>
          </div>
        {/if}

        <!-- High / Low grid - hidden for count-type commodities -->
        <div class="hl-grid" class:hidden={metrics.is_count}>
          <span class="hl-label">24h H/L</span>
          {#if metrics.high_24h !== null && metrics.low_24h !== null}
            <span class="hl-value">{fmt(metrics.high_24h)} / {fmt(metrics.low_24h)}</span>
          {:else}
            <span class="no-data">NO DATA</span>
          {/if}
          <span class="hl-label">30d H/L</span>
          {#if metrics.high_30d !== null && metrics.low_30d !== null}
            <span class="hl-value">{fmt(metrics.high_30d)} / {fmt(metrics.low_30d)}</span>
          {:else}
            <span class="no-data">NO DATA</span>
          {/if}
        </div>

        <!-- Alert threshold editor -->
        <div class="threshold-row">
          <span class="hl-label">Alert ±%</span>
          {#if editingThreshold}
            <!-- svelte-ignore a11y-autofocus -->
            <input
              class="threshold-input"
              type="number"
              min="0"
              step="0.1"
              bind:value={editValue}
              on:blur={saveThreshold}
              on:keydown={onKeydown}
              autofocus
            />
          {:else}
            <span class="threshold-value">{fmt(threshold)}</span>
            <button class="edit-btn" on:click={startEdit} title="Edit threshold">✏</button>
          {/if}
        </div>
      </div>

      <!-- Sparkline - right column, aligned with price text -->
      <div class="tile-spark">
        <SparkLine {prices} h={102} labels={true} />
      </div>
    </div>
  {/if}
</div>

<style>
  @keyframes fade-out-open {
    from { opacity: 1; }
    to   { opacity: 0; }
  }

  @keyframes tile-enter {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0);   }
  }

  @keyframes alert-pulse {
    0%, 100% {
      border-color: var(--color-alert);
      box-shadow:   0 0 14px color-mix(in srgb, var(--color-alert) var(--alert-pulse-percent), transparent);
    }
    50% {
      border-color: var(--color-neon);
      box-shadow:   0 0 22px color-mix(in srgb, var(--color-neon) var(--alert-pulse-percent), transparent);
    }
  }

  .tile {
    border:        var(--tile-border-thickness) solid var(--color-neon);
    border-radius: var(--tile-corner-radius);
    padding:       var(--tile-padding);
    background:    color-mix(in srgb, var(--color-neon) 4%, var(--color-background));
    box-shadow:    0 0 12px color-mix(in srgb, var(--color-neon) var(--glow-percent), transparent);
    transition:    border-color var(--animation-duration),
                   box-shadow   var(--animation-duration);
    animation:     tile-enter var(--animation-duration) ease-out both;
    min-width: 260px;
    flex: 1 1 260px;
  }

  .tile.alert {
    animation: alert-pulse 1.2s ease-in-out infinite;
  }

  .tile-header {
    display:       flex;
    align-items:   center;
    gap:           8px;
    margin-bottom: 10px;
  }

  .code {
    font-size:      0.8rem;
    color:          var(--color-text-secondary);
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .alert-badge {
    font-size:      0.6rem;
    padding:        2px 6px;
    border-radius:  3px;
    background:     var(--color-alert);
    color:          #fff;
    letter-spacing: 0.05em;
    font-weight:    bold;
    border:         none;
    cursor:         pointer;
    font-family:    inherit;
    transition:     opacity var(--animation-duration);
  }
  .alert-badge:hover          { opacity: 0.75; }
  .alert-badge.acknowledged   { opacity: 0.45; }

  .open-row {
    display:     flex;
    align-items: baseline;
    gap:         6px;
    margin-top:  -6px;
    margin-bottom: 8px;
    font-size:   0.78rem;
    animation:   fade-out-open 0.8s ease-out 1.5s both;
  }

  .open-label {
    color:          var(--color-text-secondary);
    font-size:      0.62rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .open-value {
    color:                var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .price-row {
    display:       flex;
    align-items:   baseline;
    gap:           10px;
    margin-bottom: 10px;
  }

  .price-value {
    display:     inline-flex;
    align-items: baseline;
    gap:         4px;
    font-size:   1.6rem;
    font-weight: bold;
    color:       var(--color-text-primary);
    transition:  color var(--animation-duration);
  }
  .price-value.up   { color: var(--color-price-up); }
  .price-value.down { color: var(--color-price-down); }

  .price-currency {
    font-size:   0.75rem;
    font-weight: normal;
    opacity:     0.7;
    align-self:  flex-end;
    padding-bottom: 0.1em;
  }

  .pct-change { font-size: 0.9rem; }
  .pct-change.up   { color: var(--color-price-up); }
  .pct-change.down { color: var(--color-price-down); }

  .last-update {
    display:     flex;
    gap:         6px;
    align-items: baseline;
    margin-bottom: 4px;
    font-size:   0.78rem;
  }

  .market-closed {
    font-size:      0.72rem;
    color:          var(--color-text-secondary);
    opacity:        0.7;
    margin-bottom:  8px;
    letter-spacing: 0.02em;
  }
  .last-label {
    color:          var(--color-text-secondary);
  }
  .last-age {
    color:               var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
  }

  .prev-row {
    display:               flex;
    align-items:           baseline;
    gap:                   6px;
    margin-bottom:         8px;
    font-size:             0.78rem;
  }
  .prev-label { color: var(--color-text-secondary); }
  .prev-value {
    color:               var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }
  .prev-time {
    color:               var(--color-text-secondary);
    font-size:           0.7rem;
    font-variant-numeric: tabular-nums;
  }

  .hl-grid {
    display:               grid;
    grid-template-columns: auto 1fr;
    gap:                   3px 10px;
    margin-bottom:         10px;
    font-size:             0.78rem;
  }

  .hl-label { color: var(--color-text-secondary); }
  .hl-value {
    color:               var(--color-text-primary);
    font-variant-numeric: tabular-nums;
  }

  .no-data {
    font-size:      0.62rem;
    font-weight:    300;
    color:          var(--color-text-secondary);
    opacity:        0.55;
    letter-spacing: 0.04em;
  }

  .tile-body {
    display:     flex;
    align-items: flex-start;
    gap:         14px;
  }

  .tile-info {
    flex:      1;
    min-width: 0;
  }

  .tile-spark {
    flex-shrink: 0;
    width:       165px;
    padding-top: 6px;   /* nudge down to sit alongside the large price text */
    opacity:     0.8;
  }

  .threshold-row {
    display:     flex;
    align-items: center;
    gap:         8px;
    font-size:   0.78rem;
  }

  .threshold-value { color: var(--color-text-primary); }

  .threshold-input {
    width:       64px;
    background:  transparent;
    border:      1px solid var(--color-neon);
    border-radius: 3px;
    color:       var(--color-text-primary);
    padding:     2px 4px;
    font-family: inherit;
    font-size:   0.78rem;
  }

  .edit-btn {
    background:  none;
    border:      none;
    cursor:      pointer;
    color:       var(--color-text-secondary);
    font-size:   0.75rem;
    padding:     0 2px;
    line-height: 1;
    transition:  color var(--animation-duration);
  }
  .edit-btn:hover { color: var(--color-neon); }

  .hidden { display: none; }

  .placeholder,
  .tile-unavailable { font-size: 0.85rem; padding: 8px 0; }
  .placeholder      { color: var(--color-text-secondary); }
  .tile-unavailable { color: var(--color-text-secondary); opacity: 0.45; font-style: italic; }
</style>
