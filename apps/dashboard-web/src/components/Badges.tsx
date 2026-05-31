const SEVERITY_HINTS: Record<string, string> = {
  S: "Severity S — may immediately move XAUUSD or risk pricing",
  A: "Severity A — may affect trading logic within hours",
  B: "Severity B — background or unconfirmed news",
  C: "Severity C — archived, not pushed"
};

const PRIORITY_HINTS: Record<string, string> = {
  P0: "Priority P0 — highest-priority source",
  P1: "Priority P1 — high-priority source",
  P2: "Priority P2 — standard source",
  P3: "Priority P3 — low-priority source"
};

export function SeverityBadge({ value }: { value?: string | null }) {
  const tone =
    value === "S"
      ? "badge-error"
      : value === "A"
        ? "badge-warning"
        : value === "B"
          ? "badge-info"
          : "badge-neutral";

  return (
    <span className={`badge ${tone} badge-sm font-semibold`} title={SEVERITY_HINTS[value ?? "C"] ?? "Event severity"}>
      {value ?? "C"}
    </span>
  );
}

export function StatusBadge({ value }: { value?: string | null }) {
  const tone =
    value === "healthy" || value === "completed" || value === "completed_truncated" || value === "sent"
      ? "badge-success"
      : value === "failed"
        ? "badge-error"
        : value === "running" || value === "retry"
          ? "badge-warning"
          : "badge-ghost";

  return (
    <span className={`badge ${tone} badge-sm`} title={`Status: ${value ?? "unknown"}`}>
      {value ?? "unknown"}
    </span>
  );
}

export function PriorityBadge({ value }: { value?: string | null }) {
  const tone = value === "P0" ? "badge-error" : value === "P1" ? "badge-warning" : "badge-outline";
  return (
    <span className={`badge ${tone} badge-sm`} title={PRIORITY_HINTS[value ?? ""] ?? "Source priority tier"}>
      {value ?? "-"}
    </span>
  );
}

export function OfficialBadge({ value }: { value?: string | null }) {
  return (
    <span className="badge badge-outline badge-sm" title={`Source official level: ${value ?? "unknown"}`}>
      {value ?? "unknown"}
    </span>
  );
}
