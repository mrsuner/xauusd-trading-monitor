import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { SeverityBadge, OfficialBadge, PriorityBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Score, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";
import { eventSummary } from "../utils/eventTranslations";

export function Events() {
  const { i18n, t } = useTranslation();
  const [severity, setSeverity] = useState("");
  const query = useQuery({
    queryKey: ["events", severity],
    queryFn: () => api.events({ page_size: 50, severity }),
    refetchInterval: 30000
  });

  return (
    <>
      <PageHeader title={t("events.title")} description={t("events.description")} />
      <div className="mb-4 max-w-full overflow-x-auto">
        <div className="tabs tabs-box w-fit">
        {["", "S", "A", "B", "C"].map((item) => (
          <button key={item || "all"} className={`tab ${severity === item ? "tab-active" : ""}`} onClick={() => setSeverity(item)}>
            {item || t("events.all")}
          </button>
        ))}
        </div>
      </div>
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm min-w-[860px]">
          <thead>
            <tr>
              <th className="w-32">{t("events.col.time")}</th>
              <th className="w-16">{t("events.col.severity")}</th>
              <th className="w-40">{t("events.col.type")}</th>
              <th>{t("events.col.title")}</th>
              <th className="w-32">{t("events.col.source")}</th>
              <th className="w-24">{t("events.col.score")}</th>
              <th className="w-24">{t("events.col.confidence")}</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <LoadingRows columns={7} /> : null}
            {query.data?.items.length === 0 ? <EmptyRow columns={7}>{t("events.empty")}</EmptyRow> : null}
            {query.data?.items.map((event) => {
              const summary = eventSummary(event.translations, i18n.language);
              return (
              <tr key={event.id}>
                <td>{formatTime(event.detected_at)}</td>
                <td><SeverityBadge value={event.severity} /></td>
                <td><Truncate text={event.event_type} /></td>
                <td>
                  <Link className="link link-primary font-medium" to={`/events/${event.id}`}>
                    <Truncate text={event.title || summary} />
                  </Link>
                  <Truncate className="text-xs text-base-content/55" text={summary} />
                </td>
                <td>
                  <Truncate text={event.source_name || event.source_group} />
                  <div className="mt-1 flex gap-1"><OfficialBadge value={event.official_level} /><PriorityBadge value={event.priority} /></div>
                </td>
                <td><Score value={event.relevance_score} /></td>
                <td><Score value={event.confidence} /></td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
