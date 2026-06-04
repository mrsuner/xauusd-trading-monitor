import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

export function Alerts() {
  const { t } = useTranslation();
  const query = useQuery({ queryKey: ["alerts"], queryFn: () => api.alerts({ page_size: 75 }), refetchInterval: 30000 });

  return (
    <>
      <PageHeader title={t("alerts.title")} description={t("alerts.description")} />
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm min-w-[760px]">
          <thead>
            <tr>
              <th className="w-32">{t("alerts.col.created")}</th>
              <th className="w-24">{t("alerts.col.channel")}</th>
              <th className="w-24">{t("alerts.col.priority")}</th>
              <th className="w-28">{t("alerts.col.status")}</th>
              <th>{t("alerts.col.event")}</th>
              <th className="w-32">{t("alerts.col.sent")}</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <LoadingRows columns={6} /> : null}
            {query.data?.items.length === 0 ? <EmptyRow columns={6}>{t("alerts.empty")}</EmptyRow> : null}
            {query.data?.items.map((alert) => (
              <tr key={alert.id}>
                <td>{formatTime(alert.created_at)}</td>
                <td>{alert.channel}</td>
                <td>{alert.priority}</td>
                <td><StatusBadge value={alert.delivery_status} /></td>
                <td>
                  <div className="flex gap-2"><SeverityBadge value={alert.event_severity} /><Truncate className="font-medium" text={alert.event_title || alert.message} /></div>
                  <Truncate className="text-xs text-error" text={alert.error_message} />
                </td>
                <td>{formatTime(alert.sent_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
