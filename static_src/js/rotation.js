// Rotation screen: drag ordering, order serialised on save.
(function () {
  const list = document.getElementById("rotation-list");
  const form = document.getElementById("rotation-form");
  const orderInputs = document.getElementById("order-inputs");
  if (!list || !form) return;

  new Sortable(list, { handle: ".drag-handle", animation: 150 });

  form.addEventListener("submit", (event) => {
    if (event.submitter && event.submitter.name === "remove") return;
    orderInputs.innerHTML = "";
    list.querySelectorAll("[data-routine]").forEach((item) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "order";
      input.value = item.dataset.routine;
      orderInputs.appendChild(input);
    });
  });
})();
