/* ── Severity config ───────────────────────────────────────────────────────── */
export const SEV = {
  critical: { color: "#f87171", bg: "#f8717112", label: "Critical" },
  major:    { color: "#fbbf24", bg: "#fbbf2412", label: "Major"    },
  minor:    { color: "#34d399", bg: "#34d39912", label: "Minor"    },
};

/* ── Grade helper ──────────────────────────────────────────────────────────── */
export const gradeOf = (score) => {
  if (score >= 90) return { letter: "A", color: "#34d399" };
  if (score >= 75) return { letter: "B", color: "#86efac" };
  if (score >= 60) return { letter: "C", color: "#fbbf24" };
  if (score >= 40) return { letter: "D", color: "#fb923c" };
  return             { letter: "F", color: "#f87171" };
};

/* ── Rotterdam dataset samples (mock thumbnails) ───────────────────────────── */
export const ROTTERDAM_SAMPLES = [
  { id: 1, name: "RTM — 0042", label: "inaccessible", scene: "Sidewalk", img: "https://images.unsplash.com/photo-1605559424843-9e4c228bf1c2?w=400&q=75" },
  { id: 2, name: "RTM — 0118", label: "accessible",   scene: "Entrance", img: "https://images.unsplash.com/photo-1587829741301-dc798b83add3?w=400&q=75" },
  { id: 3, name: "RTM — 0203", label: "inaccessible", scene: "Parking",  img: "https://images.unsplash.com/photo-1506521781263-d8422e82f27a?w=400&q=75" },
  { id: 4, name: "RTM — 0311", label: "accessible",   scene: "Hallway",  img: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&q=75" },
  { id: 5, name: "RTM — 0407", label: "inaccessible", scene: "Stairway", img: "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=400&q=75" },
  { id: 6, name: "RTM — 0512", label: "accessible",   scene: "Sidewalk", img: "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=400&q=75" },
];

/* ── Pipeline steps shown on YouTube tab ──────────────────────────────────── */
export const PIPELINE_STEPS = [
  { title: "Download",      desc: "yt-dlp fetches the video stream and metadata" },
  { title: "Frame Extract", desc: "Scene-change detection + perceptual deduplication" },
  { title: "Gemini Audit",  desc: "Vision API analyzes each frame for ADA barriers" },
  { title: "Report",        desc: "Aggregate score, severity breakdown, fix plan" },
];
