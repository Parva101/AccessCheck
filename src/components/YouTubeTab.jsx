import { useState } from "react";
import Spinner from "./ui/Spinner";
import { auditYouTube } from "../api/audit";
import { PIPELINE_STEPS } from "../data/constants";

export default function YouTubeTab({ onResult }) {
  const [url, setUrl]       = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr]       = useState("");

  const handleRun = async () => {
    const trimmed = url.trim();
    if (!trimmed) {
      setErr("Please enter a URL.");
      return;
    }
    if (!trimmed.includes("youtube.com") && !trimmed.includes("youtu.be")) {
      setErr("Must be a YouTube URL.");
      return;
    }
    setErr("");
    setLoading(true);
    try {
      const result = await auditYouTube(trimmed);
      onResult(result, trimmed);
    } catch (e) {
      setErr(e.message || "Audit failed — check the console for details.");
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* URL input row */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <label style={{
          fontSize: 12, fontWeight: 600,
          color: "var(--muted)", letterSpacing: "0.03em",
        }}>
          YouTube URL
        </label>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            value={url}
            onChange={(e) => { setUrl(e.target.value); setErr(""); }}
            onKeyDown={(e) => e.key === "Enter" && handleRun()}
            placeholder="https://youtube.com/watch?v=…"
            style={{
              flex: 1,
              background: "var(--raised)",
              color: "var(--text)",
              border: `1.5px solid ${err ? "var(--red)" : "var(--border)"}`,
              borderRadius: 8,
              padding: "11px 14px",
              fontSize: 14,
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            onFocus={(e) => {
              e.target.style.borderColor = "var(--accent)";
              e.target.style.boxShadow = "0 0 0 3px #6e6bff18";
            }}
            onBlur={(e) => {
              e.target.style.borderColor = err ? "var(--red)" : "var(--border)";
              e.target.style.boxShadow = "none";
            }}
          />
          <button
            onClick={handleRun}
            disabled={loading}
            style={{
              padding: "0 20px",
              borderRadius: 8,
              border: "none",
              background: loading ? "var(--raised)" : "var(--accent)",
              color: loading ? "var(--muted)" : "#fff",
              fontSize: 13,
              fontWeight: 600,
              opacity: loading ? 0.7 : 1,
              whiteSpace: "nowrap",
              transition: "background 0.15s, opacity 0.15s",
              boxShadow: loading ? "none" : "0 1px 8px #6e6bff40",
            }}
          >
            {loading ? "Scanning…" : "Run Audit"}
          </button>
        </div>
        {err && (
          <p style={{ fontSize: 12, color: "var(--red)" }}>{err}</p>
        )}
      </div>

      {/* Pipeline steps */}
      {!loading && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {PIPELINE_STEPS.map(({ title, desc }, i) => (
            <div key={i} style={{
              background: "var(--raised)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "13px 14px",
            }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 8, marginBottom: 5,
              }}>
                <span style={{
                  width: 20, height: 20, borderRadius: "50%",
                  background: "var(--surface)", border: "1px solid var(--border)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 10, fontWeight: 700, color: "var(--accent)",
                  fontFamily: "var(--font-mono)", flexShrink: 0,
                }}>
                  {i + 1}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
                  {title}
                </span>
              </div>
              <p style={{
                fontSize: 12, color: "var(--muted)",
                lineHeight: 1.55, paddingLeft: 28,
              }}>
                {desc}
              </p>
            </div>
          ))}
        </div>
      )}

      {loading && <Spinner label="Analyzing video with Gemini Vision…" />}
    </div>
  );
}
