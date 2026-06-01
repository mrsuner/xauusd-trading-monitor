import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30000 });
  const stats = useQuery({ queryKey: ["overview"], queryFn: api.overview, refetchInterval: 30000 });

  return (
    <>
      <PageHeader title={t("overview.title")} description={t("overview.description")} />
      {health.error ? <ErrorPanel error={health.error} /> : null}
      {stats.error ? <ErrorPanel error={stats.error} /> : null}

      <div className="mb-4 rounded border border-base-300 bg-base-100 p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm text-base-content/60">{t("overview.apiHealth")}</div>
            <div className="mt-1 font-medium">{health.data?.service ?? "dashboard-api"}</div>
          </div>
          <span className={`badge ${health.data?.status === "ok" ? "badge-success" : "badge-warning"}`}>
            {health.data?.status ?? t("common.loading")}
          </span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <StatCard label={t("overview.stat.activeSources")} value={stats.data?.active_sources} />
        <StatCard label={t("overview.stat.rawItems1h")} value={stats.data?.raw_items_1h} />
        <StatCard label={t("overview.stat.rawItems24h")} value={stats.data?.raw_items_24h} />
        <StatCard label={t("overview.stat.events24h")} value={stats.data?.events_24h} />
        <StatCard label={t("overview.stat.highImpact")} value={stats.data?.high_impact_events_24h} />
        <StatCard label={t("overview.stat.failedProcessing")} value={stats.data?.failed_processing} />
        <StatCard label={t("overview.stat.failedAlerts")} value={stats.data?.failed_alerts} />
        <StatCard label={t("overview.stat.events1h")} value={stats.data?.events_1h} />
      </div>
    </>
  );
}
