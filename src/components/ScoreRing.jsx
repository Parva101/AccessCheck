import { useState, useEffect } from "react";
import { gradeOf } from "../data/constants";

export default function ScoreRing({ score }) {
  const [displayed, setDisplayed] = useState(0);
  const { letter, color } = gradeOf(score);
  const R = 44;
  const circ = 2 * Math.PI * R;
  const filled = (score / 100) * circ;

  useEffect(() => {
    let raf, start;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / 900, 1);
      setDisplayed(Math.round(p * score));
      if (p < 1) { raf = requestAnimationFrame(step); }
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [score]);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div style={{ position: "relative", width: 108, height: 108 }}>
        <svg width={108} height={108} style={{ transform: "rotate(-90deg)" }}>
          {/* Track */}
          <circle
            cx={54} cy={54} r={R}
            fill="none" stroke="var(--raised)" strokeWidth={7}
          />
          {/* Progress */}
          <circle
            cx={54} cy={54} r={R}
            fill="none" stroke={color} strokeWidth={7}
            strokeLinecap="round"
            strokeDasharray={`${filled} ${circ}`}
            style={{
              transition: "stroke-dasharray 0.05s",
              filter: `drop-shadow(0 0 4px ${color}66)`,
            }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
        }}>
          <span style={{
            fontSize: 26, fontWeight: 700, color, lineHeight: 1,
            animation: "count-up 0.5s ease both",
          }}>
            {displayed}
          </span>
          <span style={{
            fontSize: 11, color: "var(--muted)", marginTop: 1,
            fontFamily: "var(--font-mono)",
          }}>
            /100
          </span>
        </div>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color, letterSpacing: "0.04em" }}>
        Grade {letter}
      </div>
    </div>
  );
}
