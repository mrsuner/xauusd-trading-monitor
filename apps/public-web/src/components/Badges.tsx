import type { ConfirmationState, Severity } from "../api/types";
import { useI18n } from "../i18n";

export function SeverityBadge({ severity }: { severity: Severity }) {
  const t = useI18n();
  const className =
    severity === "S"
      ? "badge-primary"
      : severity === "A"
        ? "badge-outline badge-primary"
        : severity === "B"
          ? "badge-neutral"
          : "badge-ghost";

  return (
    <span
      className={`badge badge-sm font-mono font-semibold ${className}`}
      title={t.badges.severityDescriptions[severity]}
      aria-label={`${severity}: ${t.badges.severityDescriptions[severity]}`}
    >
      {severity}
    </span>
  );
}

export function ConfirmationBadge({ state }: { state: ConfirmationState | null }) {
  const t = useI18n();
  if (!state) {
    return <span className="badge badge-ghost badge-sm">{t.badges.unknown}</span>;
  }

  const className =
    state === "confirmed"
      ? "badge-success"
      : state === "partially_confirmed"
        ? "badge-warning"
        : state === "contradicted"
          ? "badge-error"
          : "badge-ghost";

  return (
    <span
      className={`badge badge-sm ${className}`}
      title={t.badges.confirmationDescriptions[state]}
      aria-label={`${t.badges.confirmation[state]}: ${t.badges.confirmationDescriptions[state]}`}
    >
      {t.badges.confirmation[state]}
    </span>
  );
}
