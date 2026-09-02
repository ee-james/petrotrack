<script>
  /** Pre-formatted price string produced by fmt(), e.g. "72.50" */
  export let value = '';

  $: chars = typeof value === 'string' ? value.split('') : [];
</script>

<!--
  Each digit character gets a vertical column of 0-9 (overflow:hidden, 1em tall).
  translateY(-N em) scrolls the column to reveal digit N.
  CSS transition fires whenever the digit changes → rolling odometer effect.
  Non-digit characters (decimal point, minus, space) are rendered statically.
-->
<span class="rp">
  {#each chars as char, i (i)}
    {#if char >= '0' && char <= '9'}
      <span class="rp-slot">
        <span class="rp-col" style="transform: translateY(-{parseInt(char)}em)">
          <span>0</span><span>1</span><span>2</span><span>3</span><span>4</span>
          <span>5</span><span>6</span><span>7</span><span>8</span><span>9</span>
        </span>
      </span>
    {:else}
      <span class="rp-sep">{char}</span>
    {/if}
  {/each}
</span>

<style>
  .rp {
    display:              inline-flex;
    align-items:          flex-end;
    line-height:          1;
    font-variant-numeric: tabular-nums;
  }

  .rp-slot {
    display:  inline-block;
    overflow: hidden;
    height:   1em;
  }

  .rp-col {
    display:        flex;
    flex-direction: column;
    /* floor at 300ms so the roll is always perceptible */
    transition:     transform max(var(--animation-duration, 400ms), 300ms)
                    cubic-bezier(0.33, 1, 0.68, 1);
  }

  .rp-col span {
    display:     block;
    height:      1em;
    line-height: 1em;
  }

  .rp-sep {
    display:     inline-block;
    line-height: 1em;
  }
</style>
