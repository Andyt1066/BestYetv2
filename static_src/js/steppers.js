// Weight steppers and select-on-focus numeric entry.
// ±2.5 kg per tap; long-press drops to ±0.5 for fine adjustment.
window.BestYet = window.BestYet || {};

window.BestYet.initSteppers = function (root) {
  root = root || document;

  function nudge(input, delta) {
    const current = parseFloat(input.value || input.placeholder || "0") || 0;
    const next = Math.round((current + delta) * 100) / 100;
    input.value = next;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  root.querySelectorAll(".set-row").forEach((row) => {
    if (row.dataset.steppersBound) return;
    row.dataset.steppersBound = "1";
    const input = row.querySelector(".weight-input");
    if (!input) return;
    const step = parseFloat(input.dataset.step || "2.5");
    const fine = 0.5;
    let longPress = false;
    let timer = null;

    function bind(button, sign) {
      button.addEventListener("pointerdown", () => {
        longPress = false;
        timer = setTimeout(() => {
          longPress = true;
        }, 400);
      });
      button.addEventListener("pointerup", () => {
        clearTimeout(timer);
        nudge(input, sign * (longPress ? fine : step));
      });
      button.addEventListener("pointerleave", () => clearTimeout(timer));
    }

    bind(row.querySelector(".step-down"), -1);
    bind(row.querySelector(".step-up"), +1);
  });

  // Tapping a numeric field selects its value for instant overwrite.
  root.querySelectorAll("input[inputmode]").forEach((input) => {
    if (input.dataset.selectBound) return;
    input.dataset.selectBound = "1";
    input.addEventListener("focus", () => input.select());
  });
};
