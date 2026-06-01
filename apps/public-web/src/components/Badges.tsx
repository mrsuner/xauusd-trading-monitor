import type { ConfirmationState, Severity } from "../api/types";

export function SeverityBadge({ severity }: { severity: Severity }) {
  const className =
    severity === "S"
      ? "badge-primary"
      : severity === "A"
        ? "badge-outline badge-primary"
        : severity === "B"
          ? "badge-neutral"
          : "badge-ghost";

  return <span className={`badge badge-sm font-mono font-semibold ${className}`}>{severity}</span>;
}

export function ConfirmationBadge({ state }: { state: ConfirmationState | null }) {
  if (!state) {
    return <span className="badge badge-ghost badge-sm">unknown</span>;
  }

  const className =
    state === "confirmed"
      ? "badge-success"
      : state === "partially_confirmed"
        ? "badge-warning"
        : state === "contradicted"
          ? "badge-error"
          : "badge-ghost";

  return <span className={`badge badge-sm ${className}`}>{state.replaceAll("_", " ")}</span>;
}
