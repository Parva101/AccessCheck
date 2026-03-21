export default function Header() {
  return (
    <header style={{
      position: "sticky", top: 0, zIndex: 50,
      background: "rgba(14,14,16,0.85)",
      backdropFilter: "blur(16px)",
      borderBottom: "1px solid var(--border)",
      padding: "0 28px",
    }}>
      <div style={{
        maxWidth: 860, margin: "0 auto", height: 58,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "linear-gradient(135deg, var(--accent), #9b87ff)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 2px 8px #6e6bff33", flexShrink: 0,
          }}>
            <svg width={17} height={17} viewBox="0 0 24 24" fill="none"
              stroke="#fff" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.35C17.25 22.15 21 17.25 21 12V7L12 2z" />
              <polyline points="9 12 11 14 15 10" />
            </svg>
          </div>
          <span style={{
            fontSize: 16, fontWeight: 700,
            color: "var(--text)", letterSpacing: "-0.02em",
          }}>
            AccessCheck
          </span>
        </div>

        {/* Status pills */}
        <div style={{ display: "flex", gap: 6 }}>
          {[["Gemini", "var(--green)"], ["FiftyOne", "var(--green)"]].map(([label, color]) => (
            <div key={label} style={{
              display: "flex", alignItems: "center", gap: 5,
              background: "var(--raised)", border: "1px solid var(--border)",
              borderRadius: 99, padding: "4px 10px",
            }}>
              <div style={{
                width: 5, height: 5, borderRadius: "50%",
                background: color, boxShadow: `0 0 5px ${color}`,
              }} />
              <span style={{ fontSize: 11, fontWeight: 500, color: "var(--muted)" }}>
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </header>
  );
}
