export default function Divider({ style = {} }) {
  return (
    <div style={{ height: 1, background: "var(--border)", ...style }} />
  );
}
