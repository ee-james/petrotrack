<script>
  export let cc   = null;   // ISO 3166-1 alpha-2 or null
  export let flag = '🌐';  // emoji fallback
  export let name = '';     // for aria-label
</script>

{#if cc}
  <span class="fi fi-{cc} flag-img" aria-label={name} title={name}></span>
{:else}
  <span class="flag-emoji" aria-label={name}>{flag}</span>
{/if}

<style>
  /* flag-icons overrides - keep flags small and sharp */
  :global(.flag-img.fi) {
    width:            20px !important;
    height:           14px !important;
    background-size:  cover !important;
    border-radius:    2px;
    flex-shrink:      0;
    display:          inline-block;
    vertical-align:   middle;
  }
  .flag-emoji {
    font-size:   0.9rem;
    line-height: 1;
    display:     inline-block;
  }
</style>
