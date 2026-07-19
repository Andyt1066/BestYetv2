// Routine builder: drag ordering, add/remove exercise rows.
(function () {
  const rows = document.getElementById("exercise-rows");
  const addButton = document.getElementById("add-exercise");
  const template = document.getElementById("empty-row-template");
  const totalForms = document.querySelector('input[name="exercises-TOTAL_FORMS"]');
  if (!rows || !totalForms) return;

  function renumberPositions() {
    let position = 0;
    rows.querySelectorAll("[data-row]").forEach((row) => {
      if (row.hidden) return;
      const positionInput = row.querySelector('input[name$="-position"]');
      if (positionInput) positionInput.value = position++;
    });
  }

  new Sortable(rows, {
    handle: ".drag-handle",
    animation: 150,
    onEnd: renumberPositions,
  });

  addButton.addEventListener("click", () => {
    const index = parseInt(totalForms.value, 10);
    const html = template.innerHTML.replaceAll("__prefix__", String(index));
    rows.insertAdjacentHTML("beforeend", html);
    totalForms.value = String(index + 1);
    renumberPositions();
    const newRow = rows.lastElementChild;
    newRow.querySelector("select")?.focus();
  });

  rows.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-row]");
    if (!removeButton) return;
    const row = removeButton.closest("[data-row]");
    const deleteInput = row.querySelector('input[name$="-DELETE"]');
    if (deleteInput) deleteInput.checked = true;
    row.hidden = true;
    renumberPositions();
  });

  document.getElementById("routine-form").addEventListener("submit", renumberPositions);
})();
