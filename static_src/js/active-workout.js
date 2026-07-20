// Active workout orchestrator: session lifecycle, set completion writes,
// picker, history sheet, finish flow. Server state is truth; every completed
// set is an idempotent upsert keyed on a client UUID.
(function () {
  const root = document.getElementById("workout");
  if (!root) return;
  const { uuid, postJSON } = window.BestYet;
  const sessionId = root.dataset.sessionId;
  const setUrl = root.dataset.setUrl;
  let sessionStarted = root.dataset.newSession !== "1";

  window.BestYet.initSteppers(root);
  window.BestYet.WakeLock.acquire();

  async function ensureSession() {
    if (sessionStarted) return;
    const body = { id: sessionId, started_at: new Date().toISOString() };
    if (root.dataset.routineId) body.routine = root.dataset.routineId;
    const resp = await postJSON(root.dataset.startUrl, body);
    if (resp.ok) sessionStarted = true;
  }

  function readRow(row, block) {
    const metric = block.dataset.metric;
    const data = {
      id: row.dataset.setId || uuid(),
      session: sessionId,
      exercise: block.dataset.exerciseId,
      position: parseInt(row.dataset.position || "0", 10),
      set_type: row.dataset.warmup ? "warmup" : "normal",
      weight_kg: row.querySelector(".weight-input").value || "0",
      completed_at: new Date().toISOString(),
    };
    if (block.dataset.superset) data.superset_group = parseInt(block.dataset.superset, 10);
    if (metric === "weight_time") {
      data.duration_seconds = parseInt(row.querySelector(".duration-input").value || "0", 10);
    } else if (metric === "weight_distance_time") {
      data.distance_m = row.querySelector(".distance-input").value || "0";
    } else {
      data.reps = parseInt(row.querySelector(".reps-input").value || "0", 10);
    }
    if (block.dataset.unilateral === "1") {
      const toggle = row.querySelector(".side-toggle");
      data.side = toggle ? toggle.dataset.side : "left";
    }
    return data;
  }

  async function completeSet(row, block) {
    await ensureSession();
    const payload = readRow(row, block);
    const resp = await postJSON(setUrl, payload);
    if (!resp.ok) {
      row.classList.add("has-error");
      return;
    }
    const result = await resp.json();
    row.dataset.setId = result.id;
    row.classList.add("is-complete");
    row.querySelector(".tick-target").classList.add(
      "bg-emerald-500",
      "border-emerald-500",
      "text-white"
    );
    if (result.pr && result.pr.any) {
      row.querySelector(".pr-badge").classList.remove("hidden");
    }
    const rest = parseInt(block.dataset.restSeconds || "0", 10);
    if (rest) window.BestYet.RestTimer.start(rest);
  }

  function addSetRow(block, opts) {
    opts = opts || {};
    const tpl = document.getElementById("set-row-template").content.cloneNode(true);
    const row = tpl.querySelector(".set-row");
    const list = block.querySelector(".set-list");
    row.dataset.position = list.querySelectorAll(".set-row").length;
    if (opts.warmup) row.dataset.warmup = "1";
    // Adjust the metric field to the block's metric (template defaults to reps).
    list.appendChild(row);
    window.BestYet.initSteppers(block);
    return row;
  }

  // --- event delegation ------------------------------------------------------
  root.addEventListener("click", (event) => {
    const tick = event.target.closest(".tick-target");
    if (tick) {
      const row = tick.closest(".set-row");
      const block = tick.closest(".exercise-block");
      if (!row.classList.contains("is-complete")) completeSet(row, block);
      return;
    }
    const sideToggle = event.target.closest(".side-toggle");
    if (sideToggle) {
      const next = sideToggle.dataset.side === "left" ? "right" : "left";
      sideToggle.dataset.side = next;
      sideToggle.textContent = next.charAt(0).toUpperCase();
      return;
    }
    const addSet = event.target.closest(".add-set");
    if (addSet) {
      addSetRow(addSet.closest(".exercise-block"));
      return;
    }
    const history = event.target.closest(".history-trigger");
    if (history) {
      openHistory(history.dataset.exerciseId);
      return;
    }
  });

  // --- history sheet ---------------------------------------------------------
  const historySheet = document.getElementById("history-sheet");
  async function openHistory(exerciseId) {
    const resp = await fetch(`/logbook/exercise/${exerciseId}/history/`);
    document.getElementById("history-body").innerHTML = await resp.text();
    historySheet.hidden = false;
  }
  document.getElementById("history-close").addEventListener("click", () => {
    historySheet.hidden = true;
  });

  // --- finish ----------------------------------------------------------------
  document.getElementById("finish-workout").addEventListener("click", async () => {
    const unticked = root.querySelectorAll(".set-row:not(.is-complete)").length;
    if (unticked > 0) {
      const ok = confirm(
        `${unticked} planned set${unticked > 1 ? "s" : ""} not completed. Finish anyway?`
      );
      if (!ok) return;
    }
    await ensureSession();
    const resp = await postJSON(`/logbook/api/session/${sessionId}/finish/`, {});
    if (resp.ok) {
      window.BestYet.WakeLock.release();
      window.location.href = "/logbook/";
    }
  });
})();
