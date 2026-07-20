// Screen Wake Lock: hold the screen on during an active session,
// re-acquire on visibility return (spec §8 interaction rules).
window.BestYet = window.BestYet || {};

window.BestYet.WakeLock = (function () {
  let sentinel = null;

  async function acquire() {
    if (!("wakeLock" in navigator)) return;
    try {
      sentinel = await navigator.wakeLock.request("screen");
    } catch (e) {
      /* denied or unsupported; the session still works */
    }
  }

  function release() {
    if (sentinel) {
      sentinel.release().catch(() => {});
      sentinel = null;
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && sentinel === null) acquire();
  });

  return { acquire, release };
})();
