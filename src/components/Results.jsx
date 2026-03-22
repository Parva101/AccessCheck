import ScoreRing from "./ScoreRing";
import IssueCard from "./IssueCard";
import Divider from "./ui/Divider";
import { SEV, gradeOf } from "../data/constants";

function StatItem({ label, value, valueColor }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{
        fontSize: 11, color: "var(--muted)", fontWeight: 500,
        letterSpacing: "0.04em", textTransform: "uppercase",
      }}>
        {label}
      </span>
      <span style={{ fontSize: 15, fontWeight: 600, color: valueColor || "var(--text)" }}>
        {value}
      </span>
    </div>
  );
}

export default function Results({ result, source, onClear }) {
  const counts = { critical: 0, major: 0, minor: 0 };
  result.issues.forEach((i) => counts[i.severity]++);
  const { color: scoreColor } = gradeOf(result.overall_score);

  return (
    <div className="fade-up" style={{
      background: "var(--surface)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      overflow: "hidden",
    }}>
      {/* Top bar */}
      <div style={{
        padding: "18px 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid var(--border)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 7, height: 7, borderRadius: "50%",
            background: "var(--green)", boxShadow: "0 0 6px #34d39966",
          }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}>
            Audit Complete
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{
            maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)",
          }}>
            {source}
          </span>
          <button
            onClick={onClear}
            style={{
              background: "none", border: "1px solid var(--border)",
              borderRadius: 6, padding: "4px 10px",
              fontSize: 11, fontWeight: 500, color: "var(--muted)",
              transition: "all 0.15s",
            }}
            onMouseEnter={(e) => { e.target.style.borderColor = "var(--red)"; e.target.style.color = "var(--red)"; }}
            onMouseLeave={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.color = "var(--muted)"; }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* Score + stats */}
      <div style={{
        padding: "24px 24px 20px",
        display: "flex", gap: 28, alignItems: "center", flexWrap: "wrap",
      }}>
        <ScoreRing score={result.overall_score} />
        <div style={{ flex: 1, minWidth: 200, display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <StatItem label="Scene Type" value={result.scene_type} />
            <StatItem
              label="ADA Status"
              value={result.overall_accessible ? "Compliant" : "Non-Compliant"}
              valueColor={result.overall_accessible ? "var(--green)" : "var(--red)"}
            />
            <StatItem label="Issues Found" value={result.issues.length} />
            <StatItem label="Score" value={`${result.overall_score}/100`} valueColor={scoreColor} />
          </div>

          {/* Severity counters */}
          <div style={{ display: "flex", gap: 8 }}>
            {Object.entries(counts).map(([sev, n]) => {
              const s = SEV[sev];
              return (
                <div key={sev} style={{
                  flex: 1, padding: "10px 0", borderRadius: 8, textAlign: "center",
                  background: s.bg, border: `1px solid ${s.color}20`,
                }}>
                  <div style={{
                    fontSize: 20, fontWeight: 700, color: s.color, lineHeight: 1,
                  }}>
                    {n}
                  </div>
                  <div style={{
                    fontSize: 10, color: s.color, opacity: 0.7,
                    marginTop: 3, fontWeight: 600, letterSpacing: "0.04em",
                  }}>
                    {s.label}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <Divider />

      {/* Issues list */}
      <div style={{ padding: "20px" }}>
        <div style={{
          fontSize: 12, fontWeight: 600, color: "var(--muted)",
          textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12,
        }}>
          Detected Barriers
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {result.issues.map((issue, i) => (
            <IssueCard key={i} issue={issue} delay={i * 60} />
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={{
        padding: "12px 20px",
        borderTop: "1px solid var(--border)",
        background: "var(--bg)",
      }}>
        <span style={{
          fontSize: 11, color: "var(--subtle)",
          fontFamily: "var(--font-mono)",
        }}>
          Powered by Gemini Vision · FiftyOne · {result.issues.length} issue{result.issues.length !== 1 ? "s" : ""} flagged
        </span>
      </div>
    </div>
  );
}
