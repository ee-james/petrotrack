<script>
  import { createEventDispatcher } from 'svelte';
  import { getMetrics } from './api.js';
  import { getMeta }    from './commodityMeta.js';
  import Flag           from './Flag.svelte';

  export let countCodes  = [];
  export let refreshKey  = 0;

  const dispatch = createEventDispatcher();

  // Per-code state
  let data = {};  // code → { metrics, error, errorStatus, loading }

  const STATUS_MESSAGES = {
    not_on_plan: 'Not on your API plan',
    no_data:     'No data from provider',
    api_error:   'Provider API error',
  };

  async function loadCode(code) {
    data[code] = { ...(data[code] ?? {}), loading: true, error: null };
    try {
      const m = await getMetrics(code);
      data[code] = { metrics: m, error: null, errorStatus: null, loading: false };
      dispatch('metrics', { code, metrics: m });
    } catch (e) {
      data[code] = { metrics: null, error: true, errorStatus: e.apiStatus ?? null, loading: false };
      dispatch('metrics', { code, metrics: null, errorStatus: e.apiStatus ?? null });
    }
    data = { ...data };
  }

  // reload only when refreshKey or the code list really changes - compare a
  // joined string, not the array ref (svelte hands us a new ref every tick)
  let _lastTrigger = '';
  $: {
    const trigger = `${refreshKey}|${countCodes.join(',')}`;
    if (trigger !== _lastTrigger) {
      _lastTrigger = trigger;
      countCodes.forEach(c => loadCode(c));
    }
  }

  let now = Date.now();
  import { onMount } from 'svelte';
  onMount(() => {
    const id = setInterval(() => { now = Date.now(); }, 30_000);
    return () => clearInterval(id);
  });

  function timeAgo(iso, _now) {
    if (!iso) return '';
    const s = Math.floor((_now - new Date(iso).getTime()) / 1000);
    if (s < 60)    return `${s}s ago`;
    if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
    if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
    return `${Math.floor(s / 86400)}d ago`;
  }
</script>

<section class="count-section">
  <div class="count-heading">Activity &amp; Counts</div>
  <div class="count-grid">
    {#each countCodes as code (code)}
      {@const { cc, flag, name } = getMeta(code)}
      {@const d = data[code] ?? { loading: true }}
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div
        class="count-card"
        class:alert={d.metrics?.alert}
        on:click={() => dispatch('select', { code })}
        role="button"
        tabindex="0"
      >
        <div class="card-header">
          <Flag {cc} {flag} {name} />
          <span class="card-name">{name}</span>
          {#if d.metrics?.alert}
            <span class="card-alert">!</span>
          {/if}
        </div>

        {#if d.loading && !d.metrics}
          <div class="card-loading">…</div>
        {:else if d.error}
          <div class="card-unavailable">{STATUS_MESSAGES[d.errorStatus] ?? 'Unavailable'}</div>
        {:else if d.metrics}
          <div class="card-value">{Math.round(d.metrics.price).toLocaleString()}</div>
          {#if d.metrics.count_change !== null}
            <div
              class="card-delta"
              class:up={d.metrics.count_change >= 0}
              class:down={d.metrics.count_change < 0}
            >
              {d.metrics.count_change >= 0 ? '+' : ''}{d.metrics.count_change}
            </div>
          {/if}
          <div class="card-age">{timeAgo(d.metrics.fetched_at, now)}</div>
        {/if}
      </div>
    {/each}
  </div>
</section>

<style>
  .count-section {
    margin-top:    20px;
    border:        1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
    border-radius: var(--tile-corner-radius);
    overflow:      hidden;
  }

  .count-heading {
    padding:        6px 14px;
    font-size:      0.68rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color:          var(--color-text-secondary);
    background:     color-mix(in srgb, var(--color-neon) 4%, var(--color-background));
    border-bottom:  1px solid color-mix(in srgb, var(--color-neon) 12%, transparent);
  }

  .count-grid {
    display:               grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap:                   1px;
    background:            color-mix(in srgb, var(--color-neon) 8%, transparent);
    padding:               1px;
  }

  .count-card {
    background:  var(--color-background);
    padding:     10px 12px;
    cursor:      pointer;
    transition:  background var(--animation-duration);
    min-height:  80px;
    display:     flex;
    flex-direction: column;
    gap:         4px;
  }
  .count-card:hover {
    background: color-mix(in srgb, var(--color-neon) 5%, var(--color-background));
  }
  .count-card.alert {
    background: color-mix(in srgb, var(--color-alert) 6%, var(--color-background));
  }

  .card-header {
    display:     flex;
    align-items: center;
    gap:         5px;
  }

  .card-name  {
    font-size:      0.65rem;
    color:          var(--color-text-secondary);
    letter-spacing: 0.03em;
    flex:           1;
    min-width:      0;
    overflow:       hidden;
    text-overflow:  ellipsis;
    white-space:    nowrap;
  }

  .card-alert {
    flex-shrink:    0;
    font-size:      0.55rem;
    font-weight:    bold;
    padding:        1px 3px;
    border-radius:  2px;
    background:     var(--color-alert);
    color:          #fff;
    line-height:    1.5;
  }

  .card-value {
    font-size:            1.1rem;
    font-weight:          bold;
    color:                var(--color-text-primary);
    font-variant-numeric: tabular-nums;
    line-height:          1.1;
  }

  .card-delta {
    font-size:            0.78rem;
    font-variant-numeric: tabular-nums;
  }
  .card-delta.up   { color: var(--color-price-up); }
  .card-delta.down { color: var(--color-price-down); }

  .card-age {
    font-size:            0.62rem;
    color:                var(--color-text-secondary);
    font-variant-numeric: tabular-nums;
    margin-top:           auto;
  }

  .card-loading    { font-size: 0.75rem; color: var(--color-text-secondary); }
  .card-unavailable {
    font-size:  0.65rem;
    color:      var(--color-text-secondary);
    opacity:    0.55;
    font-style: italic;
    line-height: 1.3;
  }
</style>
