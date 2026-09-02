<script>
  // prices: array of {price, fetched_at} - newest first (as returned by /prices)
  export let prices = [];
  export let h      = 48;     // viewBox height
  export let labels = false;  // show grid lines + price labels (card view only)

  const W  = 200;   // chart area width
  const LW = 44;    // label column (only used when labels=true)

  $: PAD = labels ? 9 : 0;   // padding only needed when grid lines/labels are shown
  $: TW  = labels ? W + LW : W;

  $: data = [...prices].reverse();

  $: ({ pts, minVal, maxVal } = (() => {
    if (data.length < 2) return { pts: [], minVal: 0, maxVal: 0 };
    const vals  = data.map(p => p.price);
    const min   = Math.min(...vals);
    const max   = Math.max(...vals);
    const range = max - min;
    const chartH = h - 2 * PAD;
    if (!range) return { pts: [], minVal: min, maxVal: max };
    return {
      pts: vals.map((v, i) => ({
        x: (i / (vals.length - 1)) * W,
        y: PAD + chartH - ((v - min) / range) * chartH,
      })),
      minVal: min,
      maxVal: max,
    };
  })());

  $: polylinePoints = pts.map(p => `${p.x},${p.y}`).join(' ');

  $: fillPath = pts.length
    ? `M${pts[0].x},${pts[0].y} ` +
      pts.slice(1).map(p => `L${p.x},${p.y}`).join(' ') +
      ` L${W},${h - PAD} L0,${h - PAD} Z`
    : '';

  // Unique gradient ID per tile - avoids SVG global ID collisions
  $: gradientId = prices.length
    ? `sg-${prices[0].fetched_at.replace(/\W/g, '')}`
    : 'sg-empty';

  function fmtLabel(v) {
    if (v == null) return '';
    if (v >= 10000) return v.toFixed(0);
    if (v >= 1000)  return v.toFixed(1);
    return v.toFixed(2);
  }
</script>

<svg viewBox="0 0 {TW} {h}" width="100%" height={h} xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"   stop-color="var(--color-neon)" stop-opacity="0.25" />
      <stop offset="100%" stop-color="var(--color-neon)" stop-opacity="0"    />
    </linearGradient>
  </defs>

  {#if pts.length >= 2}
    {#if labels}
      <!-- Grid lines: top, mid, bottom -->
      <line x1="0" y1={PAD}     x2={W} y2={PAD}     stroke="var(--color-neon)" stroke-opacity="0.15" stroke-width="0.5" stroke-dasharray="3 3" />
      <line x1="0" y1={h / 2}   x2={W} y2={h / 2}   stroke="var(--color-neon)" stroke-opacity="0.10" stroke-width="0.5" stroke-dasharray="3 3" />
      <line x1="0" y1={h - PAD} x2={W} y2={h - PAD} stroke="var(--color-neon)" stroke-opacity="0.15" stroke-width="0.5" stroke-dasharray="3 3" />
    {/if}

    <!-- Area fill -->
    <path d={fillPath} fill="url(#{gradientId})" />

    <!-- Sparkline -->
    <polyline
      points={polylinePoints}
      fill="none"
      stroke="var(--color-neon)"
      stroke-width="1.5"
      stroke-linejoin="round"
      stroke-linecap="round"
    />

    {#if labels}
      <!-- Price labels: max at top, mid, min at bottom -->
      <text x={W + 5} y={PAD + 4}       font-size="12" font-weight="400" fill="var(--color-neon)" fill-opacity="0.75">{fmtLabel(maxVal)}</text>
      <text x={W + 5} y={h / 2 + 4}     font-size="12" font-weight="400" fill="var(--color-neon)" fill-opacity="0.55">{fmtLabel((maxVal + minVal) / 2)}</text>
      <text x={W + 5} y={h - PAD + 4}   font-size="12" font-weight="400" fill="var(--color-neon)" fill-opacity="0.75">{fmtLabel(minVal)}</text>
    {/if}
  {/if}
</svg>
