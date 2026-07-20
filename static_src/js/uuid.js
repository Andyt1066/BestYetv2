// Client-generated UUIDv4 for sync-ready rows (spec §2.1).
window.BestYet = window.BestYet || {};
window.BestYet.uuid = function () {
  if (crypto && crypto.randomUUID) return crypto.randomUUID();
  // Fallback for older engines; the deploy target has crypto.randomUUID.
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
  );
};

// CSRF token read from the cookie for JSON POSTs.
window.BestYet.csrfToken = function () {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? match[1] : "";
};

window.BestYet.postJSON = function (url, body) {
  return fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": window.BestYet.csrfToken(),
    },
    body: JSON.stringify(body),
  });
};
