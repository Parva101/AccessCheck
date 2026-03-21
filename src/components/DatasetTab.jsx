import { useState } from "react";
import Spinner from "./ui/Spinner";
import { auditSample } from "../api/audit";
import { ROTTERDAM_SAMPLES } from "../data/constants";

export default function DatasetTab({ onResult }) {
  const [selected, setSelected] = useState(null);
  const [loading, setLoading]   = useState(false);

  const handlePick = async (sample) => {
    if (loading) return;
    setSelected(sample.id);
    setLoading(true);
    try {
      const result = await auditSample(sample.name);
      onResult(result, sample.name);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Section header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "flex-end",
      }}>
        <div>
          <h3 style={{
            fontSize: 15, fontWeight: 600,
            color: "var(--text)", marginBottom: 2,
          }}>
            Rotterdam Accessibility Dataset
          </h3>
          <p style={{ fontSize: 12, color: "var(--muted)" }}>
            1,883 street-level images · labeled accessible / inaccessible
          </p>
        </div>
        <span style={{
          fontSize: 11, fontFamily: "var(--font-mono)",
          color: "var(--accent)", background: "#6e6bff14",
          border: "1px solid #6e6bff28", borderRadius: 6, padding: "3px 9px",
        }}>
          Showing 6
        </span>
      </div>

      {/* Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        {ROTTERDAM_SAMPLES.map((sample, i) => {
          const isAcc    = sample.label === "accessible";
          const isActive = selected === sample.id;
          return (
            <div
              key={sample.id}
              className="fade-up"
              style={{
                animationDelay: `${i * 50}ms`,
                cursor: "pointer",
                borderRadius: 9,
                overflow: "hidden",
                border: `1.5px solid ${isActive ? "var(--accent)" : "var(--border)"}`,
                background: "var(--raised)",
                transition: "all 0.18s",
                boxShadow: isActive ? "0 0 0 3px #6e6bff18" : "none",
              }}
              onClick={() => handlePick(sample)}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = "var(--border-l)";
                  e.currentTarget.style.transform = "translateY(-1px)";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.transform = "translateY(0)";
                }
              }}
            >
              {/* Thumbnail */}
              <div style={{ height: 88, position: "relative", overflow: "hidden" }}>
                <img
                  src={sample.img}
                  alt={sample.name}
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                />
                <div style={{
                  position: "absolute", inset: 0,
                  background: "linear-gradient(to bottom, transparent 40%, rgba(14,14,16,0.7))",
                }} />
                {/* Label badge */}
                <div style={{
                  position: "absolute", top: 7, right: 7,
                  fontSize: 10, fontWeight: 600, letterSpacing: "0.03em",
                  color: isAcc ? "var(--green)" : "var(--red)",
                  background: isAcc ? "#34d39918" : "#f8717118",
                  border: `1px solid ${isAcc ? "#34d39930" : "#f8717130"}`,
                  borderRadius: 99, padding: "2px 7px",
                  backdropFilter: "blur(4px)",
                }}>
                  {isAcc ? "Accessible" : "Inaccessible"}
                </div>
              </div>
              {/* Meta */}
              <div style={{ padding: "9px 11px" }}>
                <div style={{
                  fontSize: 11, fontWeight: 600, color: "var(--text)",
                  fontFamily: "var(--font-mono)", marginBottom: 2,
                }}>
                  {sample.name}
                </div>
                <div style={{ fontSize: 11, color: "var(--muted)" }}>
                  {sample.scene}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {loading && <Spinner label="Auditing sample…" />}
    </div>
  );
}
