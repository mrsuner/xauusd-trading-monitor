import type { Severity } from "../api/types";
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
