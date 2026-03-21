const API_BASE = "/api";

/**
 * Audit a YouTube video for ADA accessibility issues.
 * Calls POST /api/audit/youtube → Python backend on port 8000.
 *
 * @param {string} url - YouTube video URL
 * @returns {Promise<object>} Audit result object
 */
export async function auditYouTube(url) {
  const res = await fetch(`${API_BASE}/audit/youtube`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Server error: ${res.status}`);
  }
  return res.json();
}

/**
 * Audit a single sample from the Rotterdam dataset.
 * Calls POST /api/audit/sample → Python backend on port 8000.
 *
 * @param {string} filename - Sample filename e.g. "RTM — 0042"
 * @returns {Promise<object>} Audit result object
 */
export async function auditSample(filename) {
  const res = await fetch(`${API_BASE}/audit/sample`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Server error: ${res.status}`);
  }
  return res.json();
}
