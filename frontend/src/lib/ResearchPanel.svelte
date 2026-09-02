<script>
  import { createEventDispatcher } from 'svelte';

  export let navigateTo  = '';   // set by parent (commodity click) to trigger navigation
  export let isElectron  = false;
  export let label       = 'Browser';

  const dispatch = createEventDispatcher();

  let urlBarValue    = '';
  let currentUrl     = '';
  let darkMode       = true;
  let noImages       = false;
  let dimmer         = 100;
  let webviewEl;
  let iframeEl;
  let urlInputEl;
  let listenersSet   = false;
  let urlInputActive = false;   // true while user is editing the URL bar

  function releaseWebviewFocus() {
    if (!isElectron || !webviewEl) return;
    webviewEl.blur();
    webviewEl.executeJavaScript(
      'document.activeElement && document.activeElement.blur()'
    ).catch(() => {});
  }

  function grabUrlFocus() {
    releaseWebviewFocus();
    urlInputActive = true;
    setTimeout(() => urlInputEl?.select(), 0);
  }

  function onUrlBlur() {
    urlInputActive = false;
  }

  // ---- Dark CSS (electron webview injection) ----
  const DARK_CSS = `
    html { color-scheme: dark; }
    html, body { background-color: #181818 !important; color: #d8d8d8 !important; }
    p, li, td, th, section, article, main, aside, figcaption,
    [class*="article"], [class*="content"], [class*="story"],
    [class*="para"], [class*="text"], [class*="body"] {
      color: #d8d8d8 !important;
      background-color: #181818 !important;
    }
    strong, b, dt, [class*="bold"], [class*="headline"], [class*="hed"] {
      color: #C8A020 !important;
    }
    h1,h2,h3,h4,h5,h6 { color: #e8e8e8 !important; }
    a         { color: #6ab0f5 !important; }
    a:visited { color: #9a80d4 !important; }
    a:hover   { color: #90c8ff !important; }
    input, textarea, select {
      background: #252525 !important; color: #d8d8d8 !important;
      border-color: #484848 !important;
    }
    table, thead, tbody { background: #1e1e1e !important; }
    th { background: #272727 !important; color: #C8A020 !important; }
    tr:nth-child(even) td { background: #222 !important; }
    code, pre  { background: #252525 !important; color: #ce9178 !important; }
    blockquote { border-left-color: #555 !important; background: #1e1e1e !important; }
    hr         { border-color: #3a3a3a !important; }
    nav, header, footer { background: #202020 !important; border-color: #3a3a3a !important; }
    .card, .widget, .sidebar { background: #1e1e1e !important; }
    .mw-body, .mw-page-container { background: #181818 !important; color: #d8d8d8 !important; }
    .mw-header, #mw-head, #mw-panel { background: #202020 !important; }
    .infobox, .wikitable { background: #1e1e1e !important; border-color: #3a3a3a !important; }
    .toc, .catlinks      { background: #1e1e1e !important; border-color: #3a3a3a !important; }
  `;

  const HIDE_IMAGES_JS = `
    document.querySelectorAll('img,picture,figure,svg,canvas,video')
      .forEach(el => el.style.setProperty('display','none','important'));
    const s = document.createElement('style');
    s.textContent = '* { background-image: none !important; }';
    document.head.appendChild(s);
  `;

  // ---- Navigation ----

  function internalNavigate(url) {
    if (!url) return;
    currentUrl  = url;
    urlBarValue = url;
    if (isElectron && webviewEl) webviewEl.loadURL(url).catch(() => {});
  }

  // React to parent pushing a new URL (commodity click)
  let _lastNavigateTo = '';
  $: if (navigateTo !== _lastNavigateTo) {
    _lastNavigateTo = navigateTo;
    if (navigateTo) internalNavigate(navigateTo);
  }

  function navigate() {
    let url = urlBarValue.trim();
    if (!url) return;
    if (!/^https?:\/\//i.test(url)) url = 'https://' + url;
    internalNavigate(url);
  }

  function onKeydown(e) {
    if (e.key === 'Enter') navigate();
  }

  // ---- Webview (electron) ----

  function applyOptions() {
    if (!webviewEl) return;
    if (darkMode)  webviewEl.insertCSS(DARK_CSS).catch(() => {});
    if (noImages)  webviewEl.executeJavaScript(HIDE_IMAGES_JS).catch(() => {});
  }

  $: if (webviewEl && !listenersSet) {
    listenersSet = true;
    webviewEl.addEventListener('dom-ready', () => {
      applyOptions();
      // Release keyboard focus every time a page finishes loading so the
      // parent window's URL bar is immediately typeable without clicking first.
      releaseWebviewFocus();
    });
    webviewEl.addEventListener('did-navigate', (e) => {
      currentUrl = e.url;
      if (!urlInputActive) urlBarValue = e.url;
    });
    webviewEl.addEventListener('did-navigate-in-page', (e) => {
      if (!e.isMainFrame) return;
      currentUrl = e.url;
      if (!urlInputActive) urlBarValue = e.url;
    });
  }
  $: if (!webviewEl) listenersSet = false;

  $: if (webviewEl && currentUrl) webviewEl.loadURL(currentUrl).catch(() => {});

  // ---- Proxy iframe (web browser fallback) ----

  $: iframeSrc = currentUrl
    ? `/proxy/fetch?url=${encodeURIComponent(currentUrl)}&dark=${darkMode}&no_images=${noImages}`
    : 'about:blank';

  $: frameFilter = dimmer < 100 ? `brightness(${dimmer}%)` : 'none';
</script>

<div class="panel">
  <!-- Title bar -->
  <div class="panel-titlebar">
    <span class="panel-label">{label}</span>
    <button class="close-btn" on:click={() => dispatch('close')} title="Close panel">✕</button>
  </div>

  <!-- URL bar + options sit in a controls overlay so the webview can never cover them -->
  <div class="controls-overlay">
    <div class="url-bar">
      <button class="nav-btn" title="Back"    on:click={() => webviewEl?.goBack()}    disabled={!isElectron}>‹</button>
      <button class="nav-btn" title="Forward" on:click={() => webviewEl?.goForward()} disabled={!isElectron}>›</button>
      <input
        class="url-input"
        type="text"
        bind:this={urlInputEl}
        bind:value={urlBarValue}
        on:mousedown={grabUrlFocus}
        on:focus={grabUrlFocus}
        on:blur={onUrlBlur}
        on:keydown={onKeydown}
        spellcheck="false"
        autocomplete="off"
        placeholder="Enter a URL - or click any commodity row…"
      />
      <button class="go-btn" on:click={navigate}>Go</button>
    </div>

    <!-- Options -->
    <div class="options-bar">
    <label class="opt-toggle">
      <input type="checkbox" bind:checked={darkMode}
        on:change={() => isElectron && webviewEl?.reload()} />
      <span>Dark</span>
    </label>
    <label class="opt-toggle">
      <input type="checkbox" bind:checked={noImages}
        on:change={() => isElectron && webviewEl?.reload()} />
      <span>No images</span>
    </label>
    <label class="opt-dim">
      <span class="dim-label">Dim</span>
      <input class="dim-slider" type="range" min="20" max="100" step="2" bind:value={dimmer} />
      <span class="dim-val">{dimmer}%</span>
    </label>
  </div>
  </div><!-- end controls-overlay -->

  <!-- Browser -->
  {#if isElectron}
    <webview
      bind:this={webviewEl}
      src="about:blank"
      class="browser-frame"
      style="filter:{frameFilter}"
      allowpopups
    ></webview>
  {:else}
    <iframe
      bind:this={iframeEl}
      src={iframeSrc}
      title="Research browser"
      class="browser-frame"
      style="filter:{frameFilter}"
      sandbox="allow-scripts allow-same-origin allow-forms"
    ></iframe>
  {/if}
</div>

<style>
  .panel {
    display:        flex;
    flex-direction: column;
    gap:            6px;
    min-height:     0;
    flex:           1;
    /* visual chrome - makes it feel like an embedded app panel */
    background:     color-mix(in srgb, var(--color-neon) 4%, var(--color-background));
    border:         1px solid color-mix(in srgb, var(--color-neon) 22%, transparent);
    border-radius:  var(--tile-corner-radius);
    padding:        10px 12px;
    /* isolate stacking so url controls always sit above the iframe */
    isolation:      isolate;
  }

  .panel-titlebar {
    display:         flex;
    align-items:     center;
    justify-content: space-between;
    padding:         0 2px;
    flex-shrink:     0;
  }
  .panel-label {
    font-size:      0.62rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color:          var(--color-web-accent);
    opacity:        0.6;
  }
  .close-btn {
    background:    transparent;
    border:        none;
    color:         var(--color-text-secondary);
    cursor:        pointer;
    font-size:     0.78rem;
    padding:       2px 4px;
    opacity:       0.5;
    line-height:   1;
    transition:    opacity var(--animation-duration);
  }
  .close-btn:hover { opacity: 1; color: var(--color-alert); }

  /* Overlay keeps url bar + options strictly above the webview/iframe at all times */
  .controls-overlay {
    position:       relative;
    z-index:        100;
    flex-shrink:    0;
    display:        flex;
    flex-direction: column;
    gap:            6px;
    pointer-events: auto;
  }

  .url-bar {
    display:     flex;
    gap:         5px;
    align-items: center;
  }

  .nav-btn {
    background:    transparent;
    border:        1px solid color-mix(in srgb, var(--color-web-accent) 30%, transparent);
    border-radius: 4px;
    color:         var(--color-web-accent);
    cursor:        pointer;
    font-size:     1rem;
    line-height:   1;
    padding:       3px 8px;
    flex-shrink:   0;
    transition:    background var(--animation-duration);
  }
  .nav-btn:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-web-accent) 12%, transparent);
  }
  .nav-btn:disabled { opacity: 0.22; cursor: default; }

  .url-input {
    flex:          1;
    min-width:     0;
    background:    color-mix(in srgb, var(--color-web-accent) 5%, var(--color-background));
    border:        1px solid color-mix(in srgb, var(--color-web-accent) 30%, transparent);
    border-radius: 4px;
    color:         var(--color-text-primary);
    font-family:   inherit;
    font-size:     0.75rem;
    padding:       5px 9px;
    transition:    border-color var(--animation-duration);
  }
  .url-input:focus {
    outline:      none;
    border-color: var(--color-web-accent);
  }
  .url-input::placeholder { color: var(--color-text-secondary); opacity: 0.4; }

  .go-btn {
    background:     transparent;
    border:         1px solid var(--color-web-accent);
    border-radius:  4px;
    color:          var(--color-web-accent);
    cursor:         pointer;
    font-family:    inherit;
    font-size:      0.75rem;
    padding:        5px 12px;
    flex-shrink:    0;
    transition:     background var(--animation-duration);
  }
  .go-btn:hover { background: color-mix(in srgb, var(--color-web-accent) 14%, transparent); }

  .options-bar {
    display:     flex;
    align-items: center;
    gap:         12px;
  }
  .opt-toggle {
    display:     flex;
    align-items: center;
    gap:         4px;
    cursor:      pointer;
    font-size:   0.68rem;
    color:       var(--color-text-secondary);
    user-select: none;
  }
  .opt-toggle input[type="checkbox"] {
    accent-color: var(--color-web-accent);
    width: 12px; height: 12px; cursor: pointer;
  }
  .opt-toggle:hover span { color: var(--color-web-accent); }

  .opt-dim {
    display:     flex;
    align-items: center;
    gap:         6px;
    margin-left: auto;
  }
  .dim-label { font-size: 0.68rem; color: var(--color-text-secondary); }
  .dim-slider { width: 90px; accent-color: var(--color-web-accent); cursor: pointer; }
  .dim-val {
    font-size: 0.68rem; color: var(--color-text-secondary);
    font-variant-numeric: tabular-nums; min-width: 3ch;
  }

  .browser-frame {
    flex:          1;
    width:         100%;
    border:        1px solid color-mix(in srgb, var(--color-neon) 18%, transparent);
    border-radius: 6px;
    background:    color-mix(in srgb, var(--color-neon) 3%, var(--color-background));
    min-height:    0;
  }
</style>
