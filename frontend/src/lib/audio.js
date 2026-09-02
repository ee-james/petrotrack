// Web Audio API beep - no external files needed.
// Plays two short tones ("beep beep") when a price enters an alert condition.

let ctx = null;
let lastBeepAt = 0;
let muted = false;
const activeLoops = new Map(); // code → intervalId

export function toggleMute() { muted = !muted; return muted; }
export function isMuted()    { return muted; }

function getCtx() {
  if (!ctx) {
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch { return null; }
  }
  return ctx;
}

export async function playAlertBeep() {
  if (muted) return;
  // Global debounce - prevents pile-up if multiple tiles alert simultaneously
  const now = Date.now();
  if (now - lastBeepAt < 4000) return;
  lastBeepAt = now;

  const ac = getCtx();
  if (!ac) return;

  try {
    if (ac.state === 'suspended') await ac.resume();

    const t = ac.currentTime;
    [0, 0.22].forEach(delay => {
      const osc  = ac.createOscillator();
      const gain = ac.createGain();
      osc.connect(gain);
      gain.connect(ac.destination);

      osc.type = 'sine';
      osc.frequency.value = 880; // A5

      gain.gain.setValueAtTime(0, t + delay);
      gain.gain.linearRampToValueAtTime(0.22, t + delay + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.001, t + delay + 0.13);

      osc.start(t + delay);
      osc.stop(t + delay + 0.15);
    });
  } catch { /* audio unavailable */ }
}

export async function forceBeep() {
  lastBeepAt = 0;
  await playAlertBeep();
}

// Start a repeating beep loop for an active unacknowledged alert.
// Beeps immediately, then every 10 seconds. Safe to call repeatedly - won't double-start.
export function startAlertLoop(code) {
  if (activeLoops.has(code)) return;
  playAlertBeep();
  const id = setInterval(() => playAlertBeep(), 10_000);
  activeLoops.set(code, id);
}

// Stop the repeating loop for a code (on acknowledge or alert clearing).
export function stopAlertLoop(code) {
  const id = activeLoops.get(code);
  if (id !== undefined) {
    clearInterval(id);
    activeLoops.delete(code);
  }
}
