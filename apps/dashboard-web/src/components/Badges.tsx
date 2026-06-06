import { useTranslation } from "react-i18next";

export function SeverityBadge({ value }: { value?: string | null }) {
  const { t } = useTranslation();
  const tone =
    value === "S"
      ? "badge-error"
      : value === "A"
        ? "badge-warning"
        : value === "B"
          ? "badge-info"
          : "badge-neutral";
  const code = value ?? "C";
  const hint = t(`badges.severityHint.${code}`, { defaultValue: t("badges.severityFallback") });

  return (
    <span className={`badge ${tone} badge-sm font-semibold`} title={hint}>
      {code}
    </span>
  );
}

export function StatusBadge({ value }: { value?: string | null }) {
  const { t } = useTranslation();
  const tone =
    value === "healthy" || value === "completed" || value === "completed_truncated" || value === "sent"
      ? "badge-success"
      : value === "failed"
        ? "badge-error"
        : value === "running" || value === "retry" || value === "partial_completed"
          ? "badge-warning"
          : "badge-ghost";

  return (
    <span className={`badge ${tone} badge-sm`} title={t("badges.status", { value: value ?? "unknown" })}>
      {value ?? "unknown"}
    </span>
  );
}

export function PriorityBadge({ value }: { value?: string | null }) {
  const { t } = useTranslation();
  const tone = value === "P0" ? "badge-error" : value === "P1" ? "badge-warning" : "badge-outline";
  const hint = value ? t(`badges.priorityHint.${value}`, { defaultValue: t("badges.priorityFallback") }) : t("badges.priorityFallback");
  return (
    <span className={`badge ${tone} badge-sm`} title={hint}>
      {value ?? "-"}
    </span>
  );
}

export function OfficialBadge({ value }: { value?: string | null }) {
  const { t } = useTranslation();
  return (
    <span className="badge badge-outline badge-sm" title={t("badges.officialLevel", { value: value ?? "unknown" })}>
      {value ?? "unknown"}
    </span>
  );
}
