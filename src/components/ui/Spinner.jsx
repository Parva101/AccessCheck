export default function Spinner({ label = "Loading…" }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", gap: 14, padding: "36px 0",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%",
        border: "2.5px solid var(--border)",
        borderTopColor: "var(--accent)",
        animation: "spin 0.7s linear infinite",
      }} />
      <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 500 }}>
        {label}
      </span>
    </div>
  );
}
