import type { ReactNode } from "react";

export function Card({ title, icon, right, children, className = "" }: {
  title?: ReactNode; icon?: ReactNode; right?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border p-4 ${className}`} style={{ background: "var(--panel)", borderColor: "var(--line)" }}>
      {(title || right) && (
        <header className="mb-3 flex items-center justify-between gap-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--text)" }}>
            {icon}
            {title}
          </h3>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function Pill({ children, color = "var(--muted)", className = "" }: { children: ReactNode; color?: string; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-medium ${className}`}
      style={{ color, background: `color-mix(in srgb, ${color} 16%, transparent)`, border: `1px solid color-mix(in srgb, ${color} 30%, transparent)` }}
    >
      {children}
    </span>
  );
}

export function Dot({ color }: { color: string }) {
  return <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />;
}

export const STATUS_COLOR = { healthy: "var(--green)", warning: "var(--amber)", critical: "var(--red)" } as const;
export const SEVERITY_COLOR = { low: "var(--green)", medium: "var(--amber)", high: "var(--red)" } as const;
export const STATE_COLOR = {
  NEW: "var(--amber)", OPEN: "var(--orange)", MONITORING: "var(--blue)", RESOLVED: "var(--green)", ESCALATED: "var(--red)",
} as const;

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-4 text-center text-sm" style={{ color: "var(--faint)" }}>{children}</p>;
}

export function humanize(s: string): string {
  return s.replace(/^dtc_/, "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}
