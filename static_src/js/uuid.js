// Client-generated UUIDv4 for sync-ready rows (spec §2.1).
window.BestYet = window.BestYet || {};
window.BestYet.uuid = function () {
  if (crypto && crypto.randomUUID) return crypto.randomUUID();
  // Fallback for older engines; the deploy target has crypto.randomUUID.
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) =>
    (c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (c / 4)))).toString(16)
  );
};

// CSRF token for JSON POSTs. The cookie is HttpOnly (unreadable by JS), so the
// token is rendered into a <meta> tag; fall back to the cookie if that changes.
window.BestYet.csrfToken = function () {
  const meta = document.querySelector('meta[name="csrf-token"]');
  if (meta && meta.content) return meta.content;
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
