import Link from "next/link";

export function TopNav() {
  return (
    <header className="sticky top-0 z-10 border-b backdrop-blur" style={{ backgroundColor: "color-mix(in srgb, var(--surface-1) 92%, transparent)", borderColor: "var(--border)" }}>
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
          <span aria-hidden="true">🛰️</span>
          Smart Connected Diagnostics Platform
        </Link>
        <span className="hidden text-xs sm:inline" style={{ color: "var(--text-muted)" }}>
          LangGraph agents · single MCP server · Firestore live
        </span>
      </div>
    </header>
  );
}
