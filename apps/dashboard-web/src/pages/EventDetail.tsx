import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { OfficialBadge, SeverityBadge, StatusBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime, Score } from "../components/Format";
import { PageHeader } from "../components/Layout";

export function EventDetail() {
  const { t } = useTranslation();
  const { eventId = "" } = useParams();
  const query = useQuery({ queryKey: ["event", eventId], queryFn: () => api.event(eventId), enabled: Boolean(eventId) });
  const event = query.data;

  if (query.error) return <ErrorPanel error={query.error} />;
  if (!event) return <div className="skeleton h-40 w-full" />;

  return (
    <>
      <PageHeader title={event.title || event.event_type} description={event.summary_zh} />
      <div className="mb-4 grid gap-3 md:grid-cols-5">
        <div className="rounded border border-base-300 bg-base-100 p-3"><div className="text-xs text-base-content/50">{t("eventDetail.meta.severity")}</div><SeverityBadge value={event.severity} /></div>
        <div className="rounded border border-base-300 bg-base-100 p-3"><div className="text-xs text-base-content/50">{t("eventDetail.meta.relevance")}</div><Score value={event.relevance_score} /></div>
        <div className="rounded border border-base-300 bg-base-100 p-3"><div className="text-xs text-base-content/50">{t("eventDetail.meta.confidence")}</div><Score value={event.confidence} /></div>
        <div className="rounded border border-base-300 bg-base-100 p-3"><div className="text-xs text-base-content/50">{t("eventDetail.meta.detected")}</div>{formatTime(event.detected_at)}</div>
        <div className="rounded border border-base-300 bg-base-100 p-3"><div className="text-xs text-base-content/50">{t("eventDetail.meta.official")}</div><OfficialBadge value={event.official_level} /></div>
      </div>

      <section className="mb-4 rounded border border-base-300 bg-base-100 p-4">
        <h2 className="mb-3 font-semibold">{t("eventDetail.section.rawItems")}</h2>
        <div className="space-y-3">
          {event.raw_items.map((item) => (
            <div key={item.id} className="border-t border-base-200 pt-3 first:border-t-0 first:pt-0">
              <div className="mb-1 flex flex-wrap gap-2 text-sm"><span className="font-medium">{item.source_name}</span><span>{formatTime(item.published_at || item.ingested_at)}</span></div>
              <div className="space-y-2 text-sm text-base-content/80">
                <p className="whitespace-pre-wrap">{item.summary_zh || item.summary_en || item.text_clean || item.text_raw || item.title}</p>
                {item.summary_en ? <p className="whitespace-pre-wrap text-base-content/60">{item.summary_en}</p> : null}
                {item.full_translation_zh ? (
                  <details className="rounded border border-base-200 bg-base-200/30 p-3">
                    <summary className="cursor-pointer text-xs font-medium text-base-content/70">{t("eventDetail.chineseFullText")}</summary>
                    <p className="mt-2 whitespace-pre-wrap">{item.full_translation_zh}</p>
                  </details>
                ) : null}
                {item.full_translation_en ? (
                  <details className="rounded border border-base-200 bg-base-200/30 p-3">
                    <summary className="cursor-pointer text-xs font-medium text-base-content/70">{t("eventDetail.englishFullText")}</summary>
                    <p className="mt-2 whitespace-pre-wrap">{item.full_translation_en}</p>
                  </details>
                ) : null}
                <div className="text-xs text-base-content/50">
                  {t("eventDetail.translation")}: {item.translation_status || "pending"}
                  {item.translation_model ? ` / ${item.translation_model}` : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded border border-base-300 bg-base-100 p-4">
          <h2 className="mb-3 font-semibold">{t("eventDetail.section.claims")}</h2>
          <div className="space-y-3">
            {event.claims.length === 0 ? <div className="text-sm text-base-content/50">{t("eventDetail.noClaims")}</div> : null}
            {event.claims.map((claim) => (
              <div key={claim.id} className="border-t border-base-200 pt-3 first:border-t-0 first:pt-0">
                <div className="mb-1 flex gap-2"><StatusBadge value={claim.claim_direction} /><span className="text-sm">{claim.source_name}</span></div>
                <p className="text-sm">{claim.claim_text}</p>
              </div>
            ))}
          </div>
        </section>
        <section className="rounded border border-base-300 bg-base-100 p-4">
          <h2 className="mb-3 font-semibold">{t("eventDetail.section.alerts")}</h2>
          <div className="space-y-3">
            {event.alerts.length === 0 ? <div className="text-sm text-base-content/50">{t("eventDetail.noAlerts")}</div> : null}
            {event.alerts.map((alert) => (
              <div key={alert.id} className="border-t border-base-200 pt-3 first:border-t-0 first:pt-0">
                <div className="mb-1 flex gap-2"><StatusBadge value={alert.delivery_status} /><span className="text-sm">{alert.channel}</span><span className="text-sm">{alert.priority}</span></div>
                <p className="text-sm text-base-content/70">{alert.error_message || alert.message}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
