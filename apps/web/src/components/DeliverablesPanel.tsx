const DELIVERABLES = [
  {
    title: "Telemetry ingestion & optimized storage",
    detail: "Simulated/real asset telemetry streams in continuously and is written to per-asset time-series collections.",
    where: "Telemetry charts on any asset's detail page",
  },
  {
    title: "Real-time / near-real-time monitoring",
    detail: "Every panel here is a live Firestore listener, not a poll — no refresh needed.",
    where: "Watch the risk meter and charts move as you look at them",
  },
  {
    title: "Issue detection, alerting & recommendations",
    detail: "Rule-based + ML anomaly detection creates an issue with an AI-written explanation and a knowledge-base-grounded recommendation.",
    where: "Issue timeline (asset page) + Notifications feed",
  },
  {
    title: "Automatic resolution when normal conditions return",
    detail: "A background job re-checks open issues against fresh telemetry and auto-resolves once metrics stay normal — nobody closes it manually.",
    where: "State history inside each issue card",
  },
  {
    title: "Visibility via dashboards & notifications",
    detail: "Fleet-wide health cards, per-asset detail views, and a filterable, chronological notification feed.",
    where: "This page, and the Notifications panel",
  },
];

export function DeliverablesPanel() {
  return (
    <details
      open
      className="group rounded-xl p-5"
      style={{ backgroundColor: "var(--surface-1)", border: "1px solid var(--border)" }}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
        What this platform delivers
        <span className="text-xs font-normal transition-transform group-open:rotate-180" style={{ color: "var(--text-muted)" }}>
          ▾
        </span>
      </summary>
      <ul className="mt-4 space-y-4">
        {DELIVERABLES.map((d, i) => (
          <li key={d.title} className="flex items-start gap-3">
            <span
              className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white"
              style={{ backgroundColor: "var(--status-good)" }}
              aria-hidden="true"
            >
              {i + 1}
            </span>
            <div className="min-w-0">
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                {d.title}
              </h3>
              <p className="mt-0.5 text-xs" style={{ color: "var(--text-secondary)" }}>
                {d.detail}
              </p>
              <p className="mt-0.5 text-xs italic" style={{ color: "var(--text-muted)" }}>
                → {d.where}
              </p>
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
