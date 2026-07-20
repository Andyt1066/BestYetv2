// Rest timer: client-side countdown with vibration + audio cue at zero.
window.BestYet = window.BestYet || {};

window.BestYet.RestTimer = (function () {
  const el = document.getElementById("rest-timer");
  const remainingEl = document.getElementById("rest-remaining");
  const skipEl = document.getElementById("rest-skip");
  let interval = null;
  let endsAt = 0;

  function fmt(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
  }

  function tick() {
    const left = Math.max(0, Math.round((endsAt - Date.now()) / 1000));
    remainingEl.textContent = fmt(left);
    if (left <= 0) finish();
  }

  function finish() {
    clearInterval(interval);
    interval = null;
    el.hidden = true;
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      osc.connect(ctx.destination);
      osc.frequency.value = 880;
      osc.start();
      osc.stop(ctx.currentTime + 0.15);
    } catch (e) {
      /* audio is a nicety, not required */
    }
  }

  if (skipEl) skipEl.addEventListener("click", finish);

  return {
    start(seconds) {
      if (!seconds || !el) return;
      endsAt = Date.now() + seconds * 1000;
      el.hidden = false;
      tick();
      clearInterval(interval);
      interval = setInterval(tick, 250);
    },
  };
})();
