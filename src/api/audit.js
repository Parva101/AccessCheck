import { MOCK_RESULT } from "../data/constants";

const API_BASE = "/api";

/**
 * Audit a YouTube video for ADA accessibility issues.
 * Calls POST /api/audit/youtube with the video URL.
 *
 * TODO: Remove the mock delay and uncomment the real fetch once
 *       the Python backend (src/demo.py) is running on port 8000.
 *
 * @param {string} url - YouTube video URL
 * @returns {Promise<object>} Audit result object
 */
export async function auditYouTube(url) {
  // ── MOCK (remove when backend is ready) ───────────────────────────────────
  await new Promise((r) => setTimeout(r, 2800));
  return MOCK_RESULT;
  // ── REAL (uncomment when backend is ready) ────────────────────────────────
  // const res = await fetch(`${API_BASE}/audit/youtube`, {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({ url }),
  // });
  // if (!res.ok) throw new Error(`Server error: ${res.status}`);
  // return res.json();
}

/**
 * Audit a single sample from the Rotterdam dataset.
 * Calls POST /api/audit/sample with the sample filename.
 *
 * TODO: Remove the mock delay and uncomment the real fetch.
 *
 * @param {string} filename - Sample filename e.g. "RTM — 0042"
 * @returns {Promise<object>} Audit result object
 */
export async function auditSample(filename) {
  // ── MOCK ──────────────────────────────────────────────────────────────────
  await new Promise((r) => setTimeout(r, 2000));
  return MOCK_RESULT;
  // ── REAL ──────────────────────────────────────────────────────────────────
  // const res = await fetch(`${API_BASE}/audit/sample`, {
  //   method: "POST",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({ filename }),
  // });
  // if (!res.ok) throw new Error(`Server error: ${res.status}`);
  // return res.json();
}
