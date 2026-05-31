export function SeverityBadge({ value }: { value?: string | null }) {
  const tone =
    value === "S"
      ? "badge-error"
      : value === "A"
        ? "badge-warning"
        : value === "B"
          ? "badge-info"
          : "badge-neutral";

  return <span className={`badge ${tone} badge-sm font-semibold`}>{value ?? "C"}</span>;
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

  return <span className={`badge ${tone} badge-sm`}>{value ?? "unknown"}</span>;
}

export function PriorityBadge({ value }: { value?: string | null }) {
  const tone = value === "P0" ? "badge-error" : value === "P1" ? "badge-warning" : "badge-outline";
  return <span className={`badge ${tone} badge-sm`}>{value ?? "-"}</span>;
}

export function OfficialBadge({ value }: { value?: string | null }) {
  return <span className="badge badge-outline badge-sm">{value ?? "unknown"}</span>;
}
