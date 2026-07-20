// Plate calculator popover. Fetches the per-side breakdown from the server
// (which is the tested source of truth) and renders it. Display-only.
window.BestYet = window.BestYet || {};

window.BestYet.PlateCalc = (function () {
  const popover = document.getElementById("plate-popover");
  const body = document.getElementById("plate-body");
  const weightLabel = document.getElementById("plate-weight");
  const closeBtn = document.getElementById("plate-close");
  const root = document.getElementById("workout");

  if (closeBtn) closeBtn.addEventListener("click", () => (popover.hidden = true));

  async function open(exerciseId, weight) {
    if (!popover) return;
    weightLabel.textContent = `${weight} kg`;
    const url = `${root.dataset.platesUrl}?exercise=${exerciseId}&weight=${weight}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      body.textContent = "Plate calculator is available for barbell lifts only.";
      popover.hidden = false;
      return;
    }
    const data = await resp.json();
    if (data.achievable) {
      const chips = data.per_side
        .map(
          (p) =>
            `<span class="inline-block rounded-full bg-zinc-200 px-3 py-1 font-semibold dark:bg-zinc-700">${p}</span>`
        )
        .join(" ");
      body.innerHTML = `<p class="mb-2 text-zinc-500">Per side:</p><div class="flex flex-wrap gap-2">${chips || "just the bar"}</div>`;
    } else if (data.nearest_below || data.nearest_above) {
      body.innerHTML = `<p>Not loadable with your plates. Nearest: <strong>${data.nearest_below || "—"}</strong> or <strong>${data.nearest_above || "—"}</strong> kg.</p>`;
    } else {
      body.innerHTML = `<p>Below the bar weight.</p>`;
    }
    popover.hidden = false;
  }

  return { open };
})();
