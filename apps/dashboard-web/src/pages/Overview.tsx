import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { ErrorPanel } from "../components/DataState";
import { PageHeader } from "../components/Layout";

function StatCard({ label, value }: { label: string; value?: number | string }) {
  return (
    <div className="rounded border border-base-300 bg-base-100 p-4">
      <div className="text-xs uppercase text-base-content/50">{label}</div>
      <div className="mt-2 text-2xl font-semibold">{value ?? "-"}</div>
    </div>
  );
}

export function Overview() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30000 });
  const stats = useQuery({ queryKey: ["overview"], queryFn: api.overview, refetchInterval: 30000 });

  return (
    <>
      <PageHeader title="Overview" description="System status and recent news-layer activity." />
      {health.error ? <ErrorPanel error={health.error} /> : null}
      {stats.error ? <ErrorPanel error={stats.error} /> : null}

      <div className="mb-4 rounded border border-base-300 bg-base-100 p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-base-content/60">API health</div>
            <div className="mt-1 font-medium">{health.data?.service ?? "dashboard-api"}</div>
          </div>
          <span className={`badge ${health.data?.status === "ok" ? "badge-success" : "badge-warning"}`}>
            {health.data?.status ?? "loading"}
          </span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <StatCard label="Active Sources" value={stats.data?.active_sources} />
        <StatCard label="Raw Items 1h" value={stats.data?.raw_items_1h} />
        <StatCard label="Raw Items 24h" value={stats.data?.raw_items_24h} />
        <StatCard label="Events 24h" value={stats.data?.events_24h} />
        <StatCard label="S/A Events 24h" value={stats.data?.high_impact_events_24h} />
        <StatCard label="Failed Processing" value={stats.data?.failed_processing} />
        <StatCard label="Failed Alerts" value={stats.data?.failed_alerts} />
        <StatCard label="Events 1h" value={stats.data?.events_1h} />
      </div>
    </>
  );
}
