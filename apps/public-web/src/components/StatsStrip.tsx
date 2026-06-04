import { Activity, Radio, ShieldAlert } from "lucide-react";
import type { OverviewStats } from "../api/types";
import { formatTime } from "./format";

export function StatsStrip({ stats }: { stats?: OverviewStats }) {
  const items = [
    { label: "Public events", value: stats?.total_events ?? "—", icon: Activity },
    { label: "S severity", value: stats?.s_events ?? "—", icon: ShieldAlert },
    { label: "A severity", value: stats?.a_events ?? "—", icon: Radio },
    { label: "Latest", value: stats?.latest_event_time ? formatTime(stats.latest_event_time) : "—", icon: Activity }
  ];

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-box border border-base-300 bg-base-200/50 p-3">
          <div className="flex items-center gap-2 text-xs text-base-content/55">
            <item.icon className="h-3.5 w-3.5 text-primary" />
            {item.label}
          </div>
          <div className="mt-2 font-mono text-lg font-semibold">{item.value}</div>
        </div>
      ))}
    </div>
  );
}
