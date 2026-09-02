<script>
  import { onMount, onDestroy } from 'svelte';
  import { getConfig, getLastRefresh, putEnabledCommodities } from './lib/api.js';
  import { applyTheme } from './lib/theme.js';
  import Tile          from './lib/Tile.svelte';
  import ListRow       from './lib/ListRow.svelte';
  import ConfigPanel   from './lib/ConfigPanel.svelte';
  import CountGrid     from './lib/CountGrid.svelte';
  import ResearchPanel from './lib/ResearchPanel.svelte';
  import InsightsPanel from './lib/InsightsPanel.svelte';
  import { getMeta }   from './lib/commodityMeta.js';
  import { toggleMute, isMuted } from './lib/audio.js';

  let codes        = [];
  let metricsCache = {};

  // Sort / filter state
  let sortBy     = 'none';
  let sortDir    = 1;
  let filterText = '';

  const COUNT_PATTERN = /RIG_COUNT|FRAC_SPREAD|WELL_PERMIT|DUC_WELL|WELLS_DRILLED|WELLS_COMPLETED|_STORAGE|SPREAD_COUNT/;
  $: priceCodes = codes.filter(c => !COUNT_PATTERN.test(c));
  $: countCodes = codes.filter(c =>  COUNT_PATTERN.test(c));

  $: displayPriceCodes = (() => {
    const ft = filterText.trim().toLowerCase();
    let filtered = priceCodes.filter(c => {
      if (!ft) return true;
      const { name, flag } = getMeta(c);
      return name.toLowerCase().includes(ft) || flag.includes(ft) || c.toLowerCase().includes(ft);
    });

    const available   = filtered.filter(c => metricsCache[c] !== null || metricsCache[c] === undefined);
    const unavailable = filtered.filter(c => metricsCache[c] === null);

    function sortFn(a, b) {
      if (sortBy === 'none') return 0;
      const ma = metricsCache[a], mb = metricsCache[b];
      if (sortBy === 'name')    return sortDir * getMeta(a).name.localeCompare(getMeta(b).name);
      if (sortBy === 'country') return sortDir * getMeta(a).flag.localeCompare(getMeta(b).flag);
      if (sortBy === 'alert')   return sortDir * ((mb?.alert ? 1 : 0) - (ma?.alert ? 1 : 0));
      if (sortBy === 'price')   return sortDir * ((ma?.price ?? 0) - (mb?.price ?? 0));
      if (sortBy === 'change') {
        const ca = ma?.pct_change ?? ma?.count_change ?? 0;
        const cb = mb?.pct_change ?? mb?.count_change ?? 0;
        return sortDir * (ca - cb);
      }
      return 0;
    }

    return [...available.sort(sortFn), ...unavailable];
  })();

  function setSort(col) {
    if (sortBy === col) sortDir = -sortDir;
    else { sortBy = col; sortDir = col === 'alert' ? -1 : 1; }
  }

  function onMetrics(e) {
    const { code, metrics } = e.detail;
    metricsCache = { ...metricsCache, [code]: metrics ?? null };
  }

  $: codeColPx = codes.length
    ? Math.max(90, Math.min(
        codes.reduce((m, c) => Math.max(m, getMeta(c).name.length), 0) * 7.8 + 12,
        220))
    : 140;

  let featured   = [];
  let nextSlot   = 0;

  let config        = null;
  let refreshKey    = 0;
  let error         = null;
  let configOpen    = false;
  let duplicateCode = null;

  let timeoutId  = null;
  let intervalId = null;

  let cooldownUntil     = 0;
  let nowMs             = Date.now();
  let countdownInterval = null;

  $: manualCooldown = nowMs < cooldownUntil;
  $: cooldownMins   = manualCooldown ? Math.ceil((cooldownUntil - nowMs) / 60_000) : 0;

  // ---- Fullscreen + responsive width ----
  const isElectron = typeof window !== 'undefined' && !!window.__ELECTRON__;

  let isFullscreen  = false;
  let windowWidth   = typeof window !== 'undefined' ? window.innerWidth : 1920;
  let windowHeight  = typeof window !== 'undefined' ? window.innerHeight : 1080;

  // Show insights column when there's room: list + browser + insights (min 360) + gaps
  $: showInsights = browserPanels.length > 0 && windowWidth > (listMaxPx + browserWidth + 400);

  // Responsive list max width: scales with viewport, clamped 480-900px
  $: listMaxPx = Math.max(480, Math.min(900, Math.round(windowWidth * 0.28)));

  // Browser width clamped to at most 60% of window
  $: maxBrowserW = Math.floor(windowWidth * 0.60);

  // Cards toggle - persisted
  let showCards = (() => {
    try { return localStorage.getItem('petrotrack:showCards') !== 'false'; } catch { return true; }
  })();
  $: try { localStorage.setItem('petrotrack:showCards', String(showCards)); } catch {}

  // Mute state
  let muted = false;
  function handleMuteToggle() { muted = toggleMute(); }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }

  // ---- Browser panels ----
  let browserPanels = [];   // [{ id, navigateTo }]
  let nextPanelId   = 0;

  let browserWidth = (() => {
    try { return parseInt(localStorage.getItem('petrotrack:browserWidth') ?? '680', 10) || 680; } catch { return 680; }
  })();
  $: try { localStorage.setItem('petrotrack:browserWidth', String(browserWidth)); } catch {}

  function addBrowser() {
    if (browserPanels.length >= 2) return;
    browserPanels = [...browserPanels, { id: nextPanelId++, navigateTo: '' }];
  }

  function removeBrowser(id) {
    browserPanels = browserPanels.filter(p => p.id !== id);
  }

  function startResize(e) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = browserWidth;
    function onMove(ev) {
      browserWidth = Math.max(300, Math.min(maxBrowserW, startW + (startX - ev.clientX)));
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
    document.body.style.cursor    = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // ---- Config loading ----

  function startCooldown() {
    const ms = (config?.behavior?.manual_refresh_minutes ?? 6) * 60_000;
    cooldownUntil = Date.now() + ms;
    if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
    countdownInterval = setInterval(() => {
      nowMs = Date.now();
      if (nowMs >= cooldownUntil) { clearInterval(countdownInterval); countdownInterval = null; }
    }, 1000);
  }

  async function loadConfig() {
    try {
      config = await getConfig();
      applyTheme(config);

      const newCodes = config.commodities.enabled;

      if (!codes.length) {
        // First load - try to restore featured from localStorage
        let restoredFeatured = null;
        try {
          const saved = localStorage.getItem('petrotrack:featured');
          if (saved) {
            const parsed = JSON.parse(saved);
            const valid  = parsed.filter(c => newCodes.includes(c));
            if (valid.length > 0) restoredFeatured = valid;
          }
        } catch {}

        if (restoredFeatured) {
          featured = restoredFeatured.slice(0, 2);
          if (featured.length < Math.min(2, newCodes.length)) {
            const pool = newCodes.filter(c => !featured.includes(c));
            featured = [...featured, ...pool].slice(0, 2);
          }
        } else {
          featured = newCodes.slice(0, Math.min(2, newCodes.length));
        }
      } else {
        // Config reload - remap existing featured to new code list
        featured = featured
          .map(c => (newCodes.includes(c) ? c : null))
          .map((c, _, arr) => c ?? newCodes.find(n => !arr.includes(n)) ?? newCodes[0]);
        featured = [...new Set(featured)].slice(0, 2);
        if (featured.length < Math.min(2, newCodes.length)) {
          const pool = newCodes.filter(c => !featured.includes(c));
          featured = [...featured, ...pool].slice(0, 2);
        }
      }
      codes = newCodes;
    } catch (e) {
      error = e.message;
    }
  }

  // Persist featured tiles across sessions
  $: if (featured.length > 0) {
    try { localStorage.setItem('petrotrack:featured', JSON.stringify(featured)); } catch {}
  }

  async function scheduleAutoRefresh() {
    if (intervalId) { clearInterval(intervalId);  intervalId = null; }
    if (timeoutId)  { clearTimeout(timeoutId);    timeoutId  = null; }

    const refreshMs  = (config?.behavior?.auto_refresh_minutes  ?? 15) * 60_000;
    const cooldownMs = (config?.behavior?.manual_refresh_minutes ?? 6)  * 60_000;

    let delay = refreshMs;
    try {
      const status = await getLastRefresh();
      if (status.last_refresh_at) {
        const elapsed = Date.now() - new Date(status.last_refresh_at).getTime();
        delay = Math.max(0, refreshMs - elapsed);
        if (elapsed < cooldownMs) {
          cooldownUntil = Date.now() + (cooldownMs - elapsed);
          if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
          countdownInterval = setInterval(() => {
            nowMs = Date.now();
            if (nowMs >= cooldownUntil) { clearInterval(countdownInterval); countdownInterval = null; }
          }, 1000);
        }
      }
    } catch { /* fallback */ }

    timeoutId = setTimeout(() => {
      timeoutId = null;
      refreshKey++;
      startCooldown();
      intervalId = setInterval(() => { refreshKey++; startCooldown(); }, refreshMs);
    }, delay);
  }

  // ---- Featured-tile selection ----

  function selectForFeature(code) {
    // Drive the first browser panel to a Wikipedia search for the commodity
    if (browserPanels.length > 0) {
      const { name } = getMeta(code);
      const url = `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(name + ' commodity')}`;
      browserPanels = browserPanels.map((p, i) => i === 0 ? { ...p, navigateTo: url } : p);
    }

    if (featured.includes(code)) {
      duplicateCode = code;
      setTimeout(() => { duplicateCode = null; }, 800);
      return;
    }
    featured[nextSlot] = code;
    featured = [...featured];
    nextSlot = 1 - nextSlot;
  }

  // ---- Manual refresh ----

  function manualRefresh() {
    if (manualCooldown) return;
    refreshKey++;
    startCooldown();
  }

  // ---- Config panel save ----

  async function handleSaveConfig(e) {
    try {
      await putEnabledCommodities(e.detail.enabled);
      configOpen = false;
      await loadConfig();
      refreshKey++;
      await scheduleAutoRefresh();
    } catch (err) {
      console.error('Failed to save commodities', err);
    }
  }

  async function handleSaveTheme() {
    configOpen = false;
    await loadConfig();
  }

  // ---- Lifecycle ----

  onMount(async () => {
    await loadConfig();
    await scheduleAutoRefresh();

    const onFsChange = () => { isFullscreen = !!document.fullscreenElement; };
    const onResize   = () => {
      windowWidth  = window.innerWidth;
      windowHeight = window.innerHeight;
      // Clamp stored browser width if window shrank
      const max = Math.floor(window.innerWidth * 0.60);
      if (browserWidth > max) browserWidth = max;
    };
    document.addEventListener('fullscreenchange', onFsChange);
    window.addEventListener('resize', onResize);
    return () => {
      document.removeEventListener('fullscreenchange', onFsChange);
      window.removeEventListener('resize', onResize);
    };
  });

  onDestroy(() => {
    if (intervalId)        clearInterval(intervalId);
    if (timeoutId)         clearTimeout(timeoutId);
    if (countdownInterval) clearInterval(countdownInterval);
  });
</script>

<main
  class:fullscreen={isFullscreen}
  class:layout-1={browserPanels.length === 1}
  class:layout-2={browserPanels.length === 2}
  class:has-insights={showInsights}
  style="--browser-w: {browserWidth}px; --list-max-w: {listMaxPx}px; --win-h: {windowHeight}px"
>

  <!-- header -->
  <header class="app-header">
    <h1>PetroTrack</h1>
    <div class="header-actions">
      <button
        class="refresh-btn"
        class:cooldown={manualCooldown}
        on:click={manualRefresh}
        disabled={manualCooldown}
        title={manualCooldown ? `Next refresh available in ${cooldownMins}m` : 'Refresh all tiles now'}
      >
        {manualCooldown ? `⏳ ${cooldownMins}m` : '↻ Refresh'}
      </button>
      <button class="icon-btn" class:muted on:click={handleMuteToggle}         title={muted ? 'Unmute alerts' : 'Mute alerts'}>{muted ? '🔕' : '🔔'}</button>
      <button class="icon-btn" class:active={showCards} on:click={() => showCards = !showCards} title={showCards ? 'Hide featured tiles' : 'Show featured tiles'}>▦</button>
      <button class="icon-btn"          on:click={toggleFullscreen}             title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}>
        {isFullscreen ? '⊠' : '⛶'}
      </button>
      {#if browserPanels.length < 2}
        <button class="browser-open-btn" on:click={addBrowser}                 title="Open embedded browser">⊞ Browser</button>
      {/if}
      <button class="config-btn"        on:click={() => (configOpen = true)}    title="Configure tracked commodities">⚙</button>
    </div>
  </header>

  <!-- featured tiles -->
  {#if showCards}
    <div class="app-cards">
      <div class="featured-grid">
        {#each featured as code, i (`${i}_${code}`)}
          <Tile {code} {refreshKey} />
        {/each}
      </div>
    </div>
  {/if}

  <!-- price list + count grid -->
  <div class="app-list">
    {#if error}
      <p class="app-error">Config error: {error}</p>

    {:else if !codes.length}
      <p class="app-loading">Initializing…</p>

    {:else}
      <section class="list-section" style="--code-col-w: {codeColPx}px;">
        <div class="list-heading">
          <span>Prices</span>
          <div class="list-controls">
            <input
              class="filter-input"
              type="text"
              placeholder="Filter…"
              bind:value={filterText}
            />
            {#each [['name','Name'],['country','Country'],['alert','Alert'],['price','Price'],['change','Chg%']] as [col, label]}
              <button
                class="sort-btn"
                class:active={sortBy === col}
                on:click={() => setSort(col)}
                title="Sort by {label}"
              >{label}{sortBy === col ? (sortDir === 1 ? ' ↑' : ' ↓') : ''}</button>
            {/each}
          </div>
        </div>
        <div class="list-body">
          {#each displayPriceCodes as code (code)}
            <ListRow
              {code}
              {refreshKey}
              isDuplicate={duplicateCode === code}
              on:select={(e) => selectForFeature(e.detail.code)}
              on:metrics={onMetrics}
            />
          {/each}
        </div>
      </section>

      {#if countCodes.length}
        <CountGrid
          {countCodes}
          {refreshKey}
          on:select={(e) => selectForFeature(e.detail.code)}
          on:metrics={onMetrics}
        />
      {/if}
    {/if}
  </div>

  <!-- browser panels -->
  {#if browserPanels.length > 0}
    <div class="app-browsers">
      <div class="browser-resize-handle" on:mousedown={startResize} title="Drag to resize"></div>
      {#each browserPanels as panel, i (panel.id)}
        <ResearchPanel
          label={browserPanels.length > 1 ? `Browser ${i + 1}` : 'Browser'}
          navigateTo={panel.navigateTo}
          {isElectron}
          on:close={() => removeBrowser(panel.id)}
        />
      {/each}
    </div>
  {/if}

  {#if showInsights}
    <div class="app-insights">
      <InsightsPanel {metricsCache} {codes} />
    </div>
  {/if}

</main>

<ConfigPanel
  open={configOpen}
  currentEnabled={codes}
  on:close={() => (configOpen = false)}
  on:save={handleSaveConfig}
  on:save-theme={handleSaveTheme}
/>

<style>
  /* ---- Base layout (0 panels) ---- */
  main {
    max-width: 1200px;
    margin:    0 auto;
    padding:   clamp(16px, 2.2vh, 36px) clamp(16px, 1.8vw, 32px);
  }

  main.fullscreen {
    max-width: none;
    margin:    0;
  }

  /* ---- 1 browser panel ----
     Header spans full width at top.
     Cards row below, centered (tiles don't stretch).
     Then list on left, browser on right.
  ---- */
  main.layout-1 {
    display:               grid;
    max-width:             none;
    margin:                0;
    padding:               clamp(8px, 1.2vh, 18px) clamp(10px, 1vw, 20px);
    height:                100vh;
    row-gap:               clamp(6px, 0.8vh, 14px);
    column-gap:            clamp(40px, 5vw, 100px);
    grid-template-columns: minmax(0, var(--list-max-w, 900px)) var(--browser-w, 680px);
    grid-template-rows:    auto auto 1fr;
    grid-template-areas:
      "header  header"
      "cards   cards"
      "list    browsers";
  }

  /* ---- 2 browser panels ----
     Header + stacked cards + list on left col.
     Both browsers stacked on right col.
  ---- */
  main.layout-2 {
    display:               grid;
    max-width:             none;
    margin:                0;
    padding:               clamp(8px, 1.2vh, 18px) clamp(10px, 1vw, 20px);
    height:                100vh;
    row-gap:               clamp(6px, 0.8vh, 14px);
    column-gap:            clamp(40px, 5vw, 100px);
    grid-template-columns: minmax(0, var(--list-max-w, 900px)) var(--browser-w, 680px);
    grid-template-rows:    auto auto 1fr;
    grid-template-areas:
      "header   browsers"
      "cards    browsers"
      "list     browsers";
  }

  /* ---- Grid area assignments ---- */
  main.layout-1 .app-header,
  main.layout-2 .app-header  { grid-area: header; margin-bottom: 0; }

  main.layout-1 .app-cards,
  main.layout-2 .app-cards   { grid-area: cards; }

  main.layout-1 .app-list,
  main.layout-2 .app-list    { grid-area: list; overflow-y: auto; min-height: 0; }

  main.layout-1 .app-browsers,
  main.layout-2 .app-browsers { grid-area: browsers; display: flex; flex-direction: column; gap: 8px; min-height: 0; padding: 4px 0; position: relative; }

  /* ---- 3-column: insights panel appears when screen is wide enough ---- */
  main.layout-1.has-insights {
    grid-template-columns: minmax(0, var(--list-max-w, 900px)) var(--browser-w, 680px) 1fr;
    grid-template-areas:
      "header   header    insights"
      "cards    cards     insights"
      "list     browsers  insights";
  }

  main.layout-2.has-insights {
    grid-template-columns: minmax(0, var(--list-max-w, 900px)) var(--browser-w, 680px) 1fr;
    grid-template-areas:
      "header   browsers  insights"
      "cards    browsers  insights"
      "list     browsers  insights";
  }

  main.layout-1 .app-insights,
  main.layout-2 .app-insights { grid-area: insights; overflow-y: auto; min-height: 0; padding: 4px 0; position: relative; }

  /* Right-side separator between browser and insights - visual only */
  main.has-insights .app-insights::before {
    content:        '';
    position:       absolute;
    left:           calc(clamp(40px, 5vw, 100px) / -2 - 1px);
    top:            0;
    width:          2px;
    height:         100%;
    background:     color-mix(in srgb, var(--color-neon) 20%, transparent);
    pointer-events: none;
  }

  /* Left-side resize separator - centered in the column gap */
  .browser-resize-handle {
    position: absolute;
    /* center in gap: left edge of gap is -(column-gap), midpoint is -(column-gap/2) */
    left:     calc(clamp(40px, 5vw, 100px) / -2 - 7px);
    top:      0;
    width:    14px;
    height:   100%;
    cursor:   col-resize;
    z-index:  20;
  }
  .browser-resize-handle::after {
    content:    '';
    position:   absolute;
    left:       6px;
    top:        0;
    width:      2px;
    height:     100%;
    background: color-mix(in srgb, var(--color-neon) 22%, transparent);
    transition: background 0.15s;
  }
  .browser-resize-handle:hover::after {
    background: color-mix(in srgb, var(--color-neon) 70%, transparent);
  }

  /* Cards centered in 1-panel mode (don't stretch) */
  main.layout-1 .app-cards {
    display:         flex;
    justify-content: center;
  }

  /* Cards stacked in 2-panel mode */
  main.layout-2 .featured-grid {
    flex-direction: column;
  }

  /* ---- Header ---- */
  .app-header {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    margin-bottom:   clamp(10px, 2vh, 28px);
    flex-shrink:     0;
  }

  h1 {
    font-size:      1.25rem;
    letter-spacing: 0.18em;
    color:          var(--color-neon);
    text-transform: uppercase;
  }

  .header-actions {
    display:     flex;
    align-items: center;
    gap:         8px;
  }

  .refresh-btn {
    background:     transparent;
    border:         1px solid var(--color-neon);
    border-radius:  4px;
    color:          var(--color-neon);
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.78rem;
    padding:        5px 13px;
    letter-spacing: 0.04em;
    transition:     background var(--animation-duration),
                    color var(--animation-duration),
                    border-color var(--animation-duration);
  }
  .refresh-btn:hover:not(.cooldown) {
    background: color-mix(in srgb, var(--color-neon) 14%, transparent);
  }
  .refresh-btn.cooldown {
    border-color: var(--color-text-secondary);
    color:        var(--color-text-secondary);
    cursor:       not-allowed;
  }

  .icon-btn {
    background:    transparent;
    border:        1px solid color-mix(in srgb, var(--color-neon) 35%, transparent);
    border-radius: 4px;
    color:         var(--color-neon);
    cursor:        pointer;
    font-size:     0.82rem;
    padding:       4px 8px;
    transition:    all var(--animation-duration);
    opacity:       0.55;
  }
  .icon-btn:hover            { opacity: 1; border-color: var(--color-neon); }
  .icon-btn.active           { opacity: 1; background: color-mix(in srgb, var(--color-neon) 12%, transparent); }
  .icon-btn.muted            { opacity: 0.4; border-color: var(--color-text-secondary); color: var(--color-text-secondary); }
  .icon-btn.muted:hover      { opacity: 0.8; }

  .browser-open-btn {
    background:     transparent;
    border:         1px solid color-mix(in srgb, var(--color-neon) 45%, transparent);
    border-radius:  4px;
    color:          var(--color-neon);
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.75rem;
    letter-spacing: 0.04em;
    padding:        4px 10px;
    transition:     all var(--animation-duration);
    opacity:        0.7;
  }
  .browser-open-btn:hover { opacity: 1; background: color-mix(in srgb, var(--color-neon) 10%, transparent); }

  .config-btn {
    background:    transparent;
    border:        1px solid color-mix(in srgb, var(--color-neon) 35%, transparent);
    border-radius: 4px;
    color:         var(--color-text-secondary);
    cursor:        pointer;
    font-size:     0.88rem;
    padding:       4px 9px;
    transition:    all var(--animation-duration);
  }
  .config-btn:hover { border-color: var(--color-neon); color: var(--color-neon); }

  /* ---- Cards ---- */
  .app-cards { flex-shrink: 0; }

  .featured-grid {
    display:       flex;
    flex-wrap:     wrap;
    gap:           var(--tile-spacing);
    margin-bottom: 28px;
  }

  /* Cap individual tiles so they don't balloon on wide screens */
  .featured-grid > :global(*) {
    max-width: 460px;
    min-width: 280px;
    flex:      1;
  }

  /* In panel layouts cards are part of grid - reduce bottom margin */
  main.layout-1 .featured-grid,
  main.layout-2 .featured-grid { margin-bottom: 0; }

  /* ---- List section ---- */
  .list-section {
    border:        1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
    border-radius: var(--tile-corner-radius);
    overflow:      hidden;
  }

  .list-heading {
    display:        flex;
    align-items:    center;
    gap:            10px;
    padding:        6px 14px;
    font-size:      0.68rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color:          var(--color-text-secondary);
    background:     color-mix(in srgb, var(--color-neon) 4%, var(--color-background));
    border-bottom:  1px solid color-mix(in srgb, var(--color-neon) 12%, transparent);
    flex-wrap:      wrap;
  }

  .list-controls {
    display:     flex;
    align-items: center;
    gap:         4px;
    margin-left: auto;
    flex-wrap:   wrap;
  }

  .filter-input {
    background:    transparent;
    border:        1px solid color-mix(in srgb, var(--color-neon) 30%, transparent);
    border-radius: 3px;
    color:         var(--color-text-primary);
    font-family:   inherit;
    font-size:     0.68rem;
    padding:       2px 6px;
    width:         90px;
    transition:    border-color var(--animation-duration);
  }
  .filter-input:focus { outline: none; border-color: var(--color-neon); }
  .filter-input::placeholder { color: var(--color-text-secondary); opacity: 0.5; }

  .sort-btn {
    background:     transparent;
    border:         1px solid color-mix(in srgb, var(--color-neon) 22%, transparent);
    border-radius:  3px;
    color:          var(--color-text-secondary);
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.62rem;
    letter-spacing: 0.06em;
    padding:        2px 6px;
    transition:     all var(--animation-duration);
    text-transform: none;
  }
  .sort-btn:hover  { border-color: var(--color-neon); color: var(--color-neon); }
  .sort-btn.active { border-color: var(--color-neon); color: var(--color-neon);
                     background: color-mix(in srgb, var(--color-neon) 10%, transparent); }

  .list-body {
    display:        flex;
    flex-direction: column;
    overflow-x:     auto;  /* subtle horizontal scroll when columns are tight */
  }

  .app-error   { color: var(--color-alert); }
  .app-loading { color: var(--color-text-secondary); }

  /* ---- Global scrollbar theme ---- */
  :global(::-webkit-scrollbar)       { width: 5px; height: 5px; }
  :global(::-webkit-scrollbar-track) { background: transparent; }
  :global(::-webkit-scrollbar-thumb) {
    background:    color-mix(in srgb, var(--color-neon) 28%, transparent);
    border-radius: 3px;
  }
  :global(::-webkit-scrollbar-thumb:hover) {
    background: color-mix(in srgb, var(--color-neon) 55%, transparent);
  }
  :global(::-webkit-scrollbar-corner) { background: transparent; }
</style>
