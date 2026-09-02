<script>
  import { createEventDispatcher } from 'svelte';
  import { getAvailableCommodities, getCommoditiesCatalog, getPlanCheck, getConfig, putTheme } from './api.js';

  export let open           = false;
  export let currentEnabled = [];

  const dispatch = createEventDispatcher();

  // ---- Tab state ----
  let tab = 'commodities';   // 'commodities' | 'theme'

  // ---- Commodities tab ----
  let available     = [];
  let selected      = [];
  let loadingComm   = true;
  let refreshingCat = false;
  let saveError     = null;
  let filter        = '';
  // Set of codes confirmed unavailable on the current API plan (null = not yet checked)
  let unavailableCodes = null;

  // ---- Theme tab ----
  let loadingTheme = true;
  let themeError   = null;
  let themeSaving  = false;

  // Local editable copies of theme sections
  let colors = {};
  let motion = {};
  let tiles  = {};

  // ---- Lifecycle ----

  $: if (open) { initPanel(); }

  async function initPanel() {
    saveError  = null;
    themeError = null;
    await Promise.all([initCommodities(), initTheme()]);
  }

  async function initCommodities() {
    loadingComm = true;
    selected    = [...currentEnabled];
    filter      = '';
    try {
      const res = await getAvailableCommodities();
      // Always include currently enabled codes even if not in available list
      available = [...new Set([...res.codes, ...currentEnabled])];
    } catch (e) {
      saveError = e.message;
    } finally {
      loadingComm = false;
    }
  }

  async function initTheme() {
    loadingTheme = true;
    try {
      const cfg = await getConfig();
      // Deep-copy so edits don't affect the live config object
      colors = { ...cfg.theme.colors };
      motion = { ...cfg.theme.motion };
      tiles  = { ...cfg.theme.tiles };
    } catch (e) {
      themeError = e.message;
    } finally {
      loadingTheme = false;
    }
  }

  // ---- Commodities actions ----

  async function refreshCatalog() {
    refreshingCat = true;
    saveError = null;
    try {
      // Fetch catalog and plan availability concurrently
      const [catRes, planRes] = await Promise.all([
        getCommoditiesCatalog(),
        getPlanCheck(),
      ]);
      // Merge: catalog + currently selected so pre-selected items never vanish
      available = [...new Set([...catRes.codes, ...selected])];
      unavailableCodes = new Set(planRes.unavailable);
    } catch (e) {
      saveError = e.message;
    } finally {
      refreshingCat = false;
    }
  }

  function toggle(code) {
    if (unavailableCodes?.has(code)) return;   // not on plan - non-interactive
    if (selected.includes(code)) {
      if (selected.length > 1) selected = selected.filter(c => c !== code);
    } else {
      selected = [...selected, code];
    }
  }

  function saveCommodities() {
    if (selected.length < 1) return;
    dispatch('save', { enabled: selected });
  }

  // ---- Theme actions ----

  async function saveTheme() {
    themeSaving = true;
    themeError  = null;
    try {
      await putTheme({ colors, motion, tiles });
      dispatch('save-theme');
    } catch (e) {
      themeError = e.message;
    } finally {
      themeSaving = false;
    }
  }

  function close() {
    dispatch('close');
  }

  // ---- Helpers ----

  const COLOR_LABELS = {
    background:    'Background',
    text_primary:  'Text primary',
    text_secondary:'Text secondary',
    neon_edge:     'Accent (neon)',
    alert:         'Alert',
    price_up:      'Price up',
    price_down:    'Price down',
  };

  const MOTION_LABELS = {
    animation_duration:    'Transition (ms)',
    glow_intensity:        'Glow intensity',
    alert_pulse_intensity: 'Alert pulse',
    easing:                'Easing curve',
  };

  const TILES_LABELS = {
    border_thickness: 'Border (px)',
    corner_radius:    'Corner radius (px)',
    padding:          'Padding (px)',
    spacing:          'Spacing (px)',
  };
</script>

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="backdrop" on:click={close} />

  <aside class="panel">
    <!-- Header -->
    <div class="panel-header">
      <div class="tabs">
        <button
          class="tab-btn"
          class:active={tab === 'commodities'}
          on:click={() => (tab = 'commodities')}
        >Commodities</button>
        <button
          class="tab-btn"
          class:active={tab === 'theme'}
          on:click={() => (tab = 'theme')}
        >Theme</button>
      </div>
      <button class="close-btn" on:click={close} title="Close">✕</button>
    </div>

    <!-- commodities tab -->
    {#if tab === 'commodities'}
      {#if loadingComm}
        <p class="status">Loading…</p>
      {:else}
        <div class="comm-header">
          <span class="comm-count">{available.length} commodities</span>
          <button
            class="refresh-btn"
            on:click={refreshCatalog}
            disabled={refreshingCat}
            title="Fetch full list from OilPriceAPI"
          >{refreshingCat ? '…' : '⟳ Refresh'}</button>
        </div>
        <input
          class="filter-input"
          type="text"
          placeholder="Filter…"
          bind:value={filter}
        />
        <div class="list">
          {#each available.filter(c => !filter || c.toLowerCase().includes(filter.toLowerCase())) as code (code)}
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            {@const isUnavailable = unavailableCodes?.has(code) ?? false}
            <div
              class="item"
              class:active={selected.includes(code)}
              class:unavailable={isUnavailable}
              on:click={() => toggle(code)}
              title={isUnavailable ? 'Not available on your API plan' : undefined}
            >
              <span class="check">{selected.includes(code) ? '◉' : isUnavailable ? '✕' : '○'}</span>
              <span class="item-code">{code}</span>
              {#if isUnavailable}
                <span class="plan-tag">no plan</span>
              {/if}
            </div>
          {/each}
        </div>

        {#if saveError}
          <p class="err">{saveError}</p>
        {/if}

        <div class="footer">
          <span class="hint">{selected.length} selected</span>
          <button
            class="apply-btn"
            on:click={saveCommodities}
            disabled={selected.length < 1}
          >Apply</button>
        </div>
      {/if}

    <!-- theme tab -->
    {:else}
      {#if loadingTheme}
        <p class="status">Loading…</p>
      {:else}
        <div class="theme-scroll">

          <!-- Colors -->
          <div class="section-label">Colors</div>
          <div class="color-grid">
            {#each Object.entries(COLOR_LABELS) as [key, label]}
              <label class="color-row">
                <span class="field-label">{label}</span>
                <input
                  class="color-input"
                  type="color"
                  bind:value={colors[key]}
                />
              </label>
            {/each}
          </div>

          <!-- Motion -->
          <div class="section-label">Motion</div>
          {#each Object.entries(MOTION_LABELS) as [key, label]}
            <label class="field-row">
              <span class="field-label">{label}</span>
              {#if key === 'easing'}
                <input class="text-input" type="text" bind:value={motion[key]} />
              {:else}
                <input
                  class="num-input"
                  type="number"
                  step={key === 'animation_duration' ? 10 : 0.05}
                  min="0"
                  bind:value={motion[key]}
                />
              {/if}
            </label>
          {/each}

          <!-- Tiles -->
          <div class="section-label">Tiles</div>
          {#each Object.entries(TILES_LABELS) as [key, label]}
            <label class="field-row">
              <span class="field-label">{label}</span>
              <input
                class="num-input"
                type="number"
                step="1"
                min="0"
                bind:value={tiles[key]}
              />
            </label>
          {/each}

        </div>

        {#if themeError}
          <p class="err">{themeError}</p>
        {/if}

        <div class="footer">
          <span class="hint">{themeSaving ? 'Saving…' : ''}</span>
          <button
            class="apply-btn"
            on:click={saveTheme}
            disabled={themeSaving}
          >Apply</button>
        </div>
      {/if}
    {/if}
  </aside>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset:      0;
    background: rgba(0, 0, 0, 0.55);
    z-index:    100;
  }

  .panel {
    position:        fixed;
    top:             0;
    right:           0;
    height:          100%;
    width:           280px;
    z-index:         101;
    display:         flex;
    flex-direction:  column;
    background:      color-mix(in srgb, var(--color-neon) 5%, #111111);
    border-left:     1px solid var(--color-neon);
    padding:         16px 14px 14px;
    gap:             10px;
  }

  /* ---- Header ---- */
  .panel-header {
    display:         flex;
    justify-content: space-between;
    align-items:     center;
    flex-shrink:     0;
  }

  .tabs {
    display: flex;
    gap:     2px;
  }

  .tab-btn {
    background:     transparent;
    border:         1px solid color-mix(in srgb, var(--color-neon) 30%, transparent);
    border-radius:  3px;
    color:          var(--color-text-secondary);
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.72rem;
    letter-spacing: 0.06em;
    padding:        3px 10px;
    transition:     all var(--animation-duration);
  }
  .tab-btn.active {
    border-color: var(--color-neon);
    color:        var(--color-neon);
    background:   color-mix(in srgb, var(--color-neon) 10%, transparent);
  }
  .tab-btn:hover:not(.active) {
    color: var(--color-text-primary);
  }

  .close-btn {
    background: none;
    border:     none;
    color:      var(--color-text-secondary);
    cursor:     pointer;
    font-size:  0.9rem;
    padding:    2px 4px;
    transition: color var(--animation-duration);
  }
  .close-btn:hover { color: var(--color-alert); }

  /* ---- Commodities tab ---- */
  .comm-header {
    display:         flex;
    justify-content: space-between;
    align-items:     center;
    flex-shrink:     0;
    padding-bottom:  6px;
    border-bottom:   1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
  }

  .comm-count {
    font-size: 0.68rem;
    color:     var(--color-text-secondary);
  }

  .refresh-btn {
    background:     transparent;
    border:         1px solid color-mix(in srgb, var(--color-neon) 35%, transparent);
    border-radius:  3px;
    color:          var(--color-neon);
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.68rem;
    letter-spacing: 0.05em;
    padding:        2px 8px;
    transition:     all var(--animation-duration);
  }
  .refresh-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-neon) 12%, transparent);
  }
  .refresh-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  .filter-input {
    width:         100%;
    box-sizing:    border-box;
    background:    transparent;
    border:        1px solid color-mix(in srgb, var(--color-neon) 30%, transparent);
    border-radius: 3px;
    color:         var(--color-text-primary);
    font-family:   inherit;
    font-size:     0.72rem;
    padding:       4px 8px;
    flex-shrink:   0;
  }
  .filter-input::placeholder { color: var(--color-text-secondary); opacity: 0.6; }
  .filter-input:focus {
    outline:      none;
    border-color: var(--color-neon);
  }

  .list {
    flex:           1;
    overflow-y:     auto;
    display:        flex;
    flex-direction: column;
    gap:            3px;
  }

  .item {
    display:       flex;
    align-items:   center;
    gap:           10px;
    padding:       6px 8px;
    border-radius: 4px;
    cursor:        pointer;
    border:        1px solid transparent;
    transition:    all var(--animation-duration);
    font-size:     0.78rem;
  }
  .item:hover {
    background: color-mix(in srgb, var(--color-neon) 8%, transparent);
  }
  .item.active {
    border-color: color-mix(in srgb, var(--color-neon) 40%, transparent);
    background:   color-mix(in srgb, var(--color-neon) 8%, transparent);
  }

  .item.unavailable {
    opacity:        0.35;
    cursor:         not-allowed;
    border-color:   transparent;
    background:     transparent;
  }
  .item.unavailable:hover { background: transparent; }

  .check {
    color:     var(--color-neon);
    font-size: 0.85rem;
    width:     14px;
    flex-shrink: 0;
  }
  .item:not(.active) .check   { color: var(--color-text-secondary); }
  .item.unavailable   .check  { color: var(--color-text-secondary); }

  .item-code {
    color:          var(--color-text-primary);
    letter-spacing: 0.04em;
    font-size:      0.76rem;
    flex: 1;
  }

  .plan-tag {
    font-size:      0.58rem;
    color:          var(--color-text-secondary);
    opacity:        0.7;
    letter-spacing: 0.05em;
    flex-shrink:    0;
  }

  /* ---- Theme tab ---- */
  .theme-scroll {
    flex:       1;
    overflow-y: auto;
    display:    flex;
    flex-direction: column;
    gap:        4px;
  }

  .section-label {
    font-size:      0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color:          var(--color-neon);
    margin-top:     8px;
    margin-bottom:  2px;
    padding-bottom: 3px;
    border-bottom:  1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
  }
  .section-label:first-child { margin-top: 0; }

  .field-row,
  .color-row {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    gap:             6px;
    padding:         3px 0;
    cursor:          pointer;
  }

  .color-grid {
    display:        flex;
    flex-direction: column;
    gap:            2px;
  }

  .field-label {
    font-size:  0.72rem;
    color:      var(--color-text-secondary);
    flex:       1;
  }

  .color-input {
    width:         36px;
    height:        22px;
    border:        1px solid color-mix(in srgb, var(--color-neon) 30%, transparent);
    border-radius: 3px;
    background:    transparent;
    cursor:        pointer;
    padding:       1px;
  }

  .num-input,
  .text-input {
    width:         80px;
    background:    transparent;
    border:        1px solid color-mix(in srgb, var(--color-neon) 30%, transparent);
    border-radius: 3px;
    color:         var(--color-text-primary);
    font-family:   inherit;
    font-size:     0.72rem;
    padding:       2px 5px;
    text-align:    right;
  }
  .num-input:focus,
  .text-input:focus {
    outline:      none;
    border-color: var(--color-neon);
  }

  /* ---- Shared footer ---- */
  .footer {
    display:         flex;
    justify-content: space-between;
    align-items:     center;
    flex-shrink:     0;
    padding-top:     10px;
    border-top:      1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
  }

  .hint { font-size: 0.68rem; color: var(--color-text-secondary); }

  .apply-btn {
    background:     var(--color-neon);
    border:         none;
    border-radius:  4px;
    color:          #000;
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.73rem;
    font-weight:    bold;
    letter-spacing: 0.05em;
    padding:        5px 16px;
    transition:     opacity var(--animation-duration);
  }
  .apply-btn:disabled { opacity: 0.35; cursor: not-allowed; }
  .apply-btn:hover:not(:disabled) { opacity: 0.85; }

  .status, .err { font-size: 0.8rem; color: var(--color-text-secondary); }
  .err          { color: var(--color-alert); }
</style>
