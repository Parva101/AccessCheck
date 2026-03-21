import { useState, useRef } from "react";
import Header from "./components/Header";
import YouTubeTab from "./components/YouTubeTab";
import DatasetTab from "./components/DatasetTab";
import Results from "./components/Results";

export default function App() {
  const [tab, setTab]       = useState("youtube");
  const [result, setResult] = useState(null);
  const [source, setSource] = useState("");
  const resultsRef          = useRef(null);

  const handleResult = (r, src) => {
    setResult(r);
    setSource(src);
    setTimeout(
      () => resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      100
    );
  };

  const handleTabChange = (key) => {
    setTab(key);
    setResult(null);
  };

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--text)" }}>
      <Header />

      <main style={{
        maxWidth: 860, margin: "0 auto",
        padding: "36px 20px 80px",
        display: "flex", flexDirection: "column", gap: 24,
      }}>
        {/* Hero */}
        <div className="fade-up" style={{ paddingBottom: 4 }}>
          <h1 style={{
            fontSize: 28, fontWeight: 700,
            color: "var(--text)", letterSpacing: "-0.03em", marginBottom: 8,
          }}>
            ADA Accessibility Auditor
          </h1>
          <p style={{
            fontSize: 15, color: "var(--muted)",
            lineHeight: 1.6, maxWidth: 540,
          }}>
            Paste a YouTube property tour or browse the Rotterdam dataset —
            Gemini Vision analyzes every frame for ADA compliance barriers and
            generates a scored remediation report.
          </p>
        </div>

        {/* Input card */}
        <div
          className="fade-up"
          style={{
            animationDelay: "60ms",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          {/* Tab bar */}
          <div style={{
            display: "flex",
            borderBottom: "1px solid var(--border)",
            padding: "6px 6px 0",
          }}>
            {[
              ["youtube", "YouTube URL"],
              ["dataset", "Rotterdam Dataset"],
            ].map(([key, label]) => {
              const active = tab === key;
              return (
                <button
                  key={key}
                  onClick={() => handleTabChange(key)}
                  style={{
                    padding: "9px 16px",
                    border: "none",
                    background: "none",
                    fontSize: 13,
                    fontWeight: active ? 600 : 500,
                    color: active ? "var(--text)" : "var(--muted)",
                    borderRadius: "8px 8px 0 0",
                    borderBottom: active
                      ? "2px solid var(--accent)"
                      : "2px solid transparent",
                    marginBottom: -1,
                    transition: "all 0.15s",
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Tab content */}
          <div style={{ padding: "22px" }}>
            {tab === "youtube" ? (
              <YouTubeTab onResult={handleResult} />
            ) : (
              <DatasetTab onResult={handleResult} />
            )}
          </div>
        </div>

        {/* Results */}
        {result && (
          <div ref={resultsRef}>
            <Results
              result={result}
              source={source}
              onClear={() => setResult(null)}
            />
          </div>
        )}

        {/* Footer */}
        <p style={{
          fontSize: 11, color: "var(--subtle)", textAlign: "center",
          fontFamily: "var(--font-mono)",
        }}>
          Visual AI Hackathon · ASU 2026 · Built on FiftyOne + Gemini Vision
        </p>
      </main>
    </div>
  );
}
