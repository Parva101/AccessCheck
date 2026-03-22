export default function Badge({ label, color, bg }) {
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 9px",
      borderRadius: 99,
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: "0.02em",
      color,
      background: bg,
      border: `1px solid ${color}28`,
      fontFamily: "var(--font-mono)",
    }}>
      {label}
    </span>
  );
}
