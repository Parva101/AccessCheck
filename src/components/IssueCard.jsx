import { useState } from "react";
import Badge from "./ui/Badge";
import Divider from "./ui/Divider";
import { SEV } from "../data/constants";

export default function IssueCard({ issue, delay = 0 }) {
  const [open, setOpen] = useState(false);
  const s = SEV[issue.severity];

  return (
    <div
      className="fade-up"
      style={{
        animationDelay: `${delay}ms`,
        border: `1px solid ${open ? s.color + "30" : "var(--border)"}`,
        borderRadius: 8,
        overflow: "hidden",
        background: open ? s.bg : "var(--raised)",
        transition: "border-color 0.2s, background 0.2s",
      }}
    >
      {/* Header row */}
      <button
        onClick={() => setOpen((o) => !o)}
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 12,
          padding: "13px 16px", background: "none", border: "none",
          textAlign: "left", cursor: "pointer",
        }}
      >
        <Badge label={s.label} color={s.color} bg={s.bg} />
        <span style={{ flex: 1, fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
          {issue.issue_type}
        </span>
        {/* Chevron */}
        <svg
          width={14} height={14} viewBox="0 0 14 14" fill="none"
          style={{
            color: "var(--muted)", flexShrink: 0,
            transition: "transform 0.2s",
            transform: open ? "rotate(180deg)" : "rotate(0deg)",
          }}
        >
          <path d="M2 5l5 5 5-5" stroke="currentColor" strokeWidth={1.5}
            strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="fade-in" style={{ padding: "0 16px 14px" }}>
          <Divider />
          <p style={{
            fontSize: 13, color: "var(--muted)",
            lineHeight: 1.65, paddingTop: 10, paddingBottom: 4,
          }}>
            {issue.description}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 6 }}>
            {[
              ["Location",    issue.location_in_image],
              ["ADA Code",    issue.ada_reference],
            ].map(([key, val]) => (
              <div key={key} style={{
                background: "var(--surface)", borderRadius: 6, padding: "9px 11px",
              }}>
                <div style={{
                  fontSize: 10, color: "var(--subtle)", fontWeight: 600,
                  textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3,
                }}>
                  {key}
                </div>
                <div style={{
                  fontSize: 12, color: "var(--muted)",
                  fontFamily: "var(--font-mono)",
                }}>
                  {val}
                </div>
              </div>
            ))}
          </div>
          {/* Fix recommendation */}
          <div style={{
            background: "var(--surface)", borderRadius: 6,
            padding: "9px 11px", marginTop: 8,
            borderLeft: `3px solid ${s.color}`,
          }}>
            <div style={{
              fontSize: 10, color: "var(--subtle)", fontWeight: 600,
              textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 3,
            }}>
              Fix
            </div>
            <div style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.5 }}>
              {issue.remediation}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
