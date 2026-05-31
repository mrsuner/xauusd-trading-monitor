export function formatTime(value?: string | null) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-Hant", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(new Date(value));
}

export function Score({ value }: { value?: number | null }) {
  if (value === undefined || value === null) return <span className="text-base-content/40">-</span>;
  return <span className="font-mono text-sm">{value}</span>;
}

export function Truncate({ text, className = "" }: { text?: string | null; className?: string }) {
  return <span className={`block truncate ${className}`}>{text || "-"}</span>;
}
