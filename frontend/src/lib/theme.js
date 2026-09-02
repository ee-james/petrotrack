/**
 * applyTheme(config) - maps config.toml theme section onto CSS custom properties.
 * Called once on load and again whenever config is re-fetched.
 */
export function applyTheme(config) {
  const root   = document.documentElement;
  const { colors, motion, tiles } = config.theme;

  root.style.setProperty('--color-background',       colors.background);
  root.style.setProperty('--color-text-primary',     colors.text_primary);
  root.style.setProperty('--color-text-secondary',   colors.text_secondary);
  root.style.setProperty('--color-neon',             colors.neon_edge);
  root.style.setProperty('--color-alert',            colors.alert);
  root.style.setProperty('--color-price-up',         colors.price_up);
  root.style.setProperty('--color-price-down',       colors.price_down);
  root.style.setProperty('--color-web-accent',       colors.web_accent || '#C8A020');

  root.style.setProperty('--animation-duration',      `${motion.animation_duration}ms`);
  root.style.setProperty('--glow-intensity',          motion.glow_intensity);
  root.style.setProperty('--glow-percent',            `${Math.round(motion.glow_intensity * 100)}%`);
  root.style.setProperty('--alert-pulse-intensity',   motion.alert_pulse_intensity);
  root.style.setProperty('--alert-pulse-percent',     `${Math.round(motion.alert_pulse_intensity * 100)}%`);

  root.style.setProperty('--tile-border-thickness',  `${tiles.border_thickness}px`);
  root.style.setProperty('--tile-corner-radius',     `${tiles.corner_radius}px`);
  root.style.setProperty('--tile-padding',           `${tiles.padding}px`);
  root.style.setProperty('--tile-spacing',           `${tiles.spacing}px`);
}
