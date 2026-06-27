import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getEvent, listRawItems } from "../api/client";
import { ConfirmationBadge, SeverityBadge } from "../components/Badges";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import {
  displayCategory,
  eventSummary,
  eventTimestamp,
  eventTitle,
  formatFullTime,
  relevanceBand,
  sourceBackground,
  sourceLabel
} from "../components/format";
import { useI18n, useLanguage, useLocalizedPath } from "../i18n";
import { PageHeader } from "../components/PageHeader";
import { RawItemCard } from "../components/RawItemCard";

export function EventDetailPage() {
  const { eventId } = useParams();
  const lang = useLanguage();
  const t = useI18n();
  const to = useLocalizedPath();
  const query = useQuery({
    queryKey: ["public-event", eventId, lang],
    queryFn: () => getEvent(eventId ?? "", lang),
    enabled: Boolean(eventId)
  });
  const rawItemsQuery = useQuery({
    queryKey: ["public-event-raw-items", eventId, lang],
    queryFn: () => listRawItems({ event_id: eventId, lang, page_size: 6 }),
    enabled: Boolean(eventId)
  });

  if (!eventId) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <EmptyState title={t.detail.missingIdTitle} body={t.detail.missingIdBody} />
      </section>
    );
  }

  if (query.isLoading) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <LoadingState label={t.detail.loading} />
      </section>
    );
  }

  if (query.isError) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <ErrorState message={(query.error as Error).message} />
      </section>
    );
  }

  const event = query.data;
  if (!event) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <EmptyState title={t.detail.notFoundTitle} body={t.detail.notFoundBody} />
      </section>
    );
  }

  const relevance = relevanceBand(event.relevance_score, t);
  const timestamp = eventTimestamp(event);

  return (
    <>
      <PageHeader
        eyebrow={t.detail.eyebrow}
        title={eventTitle(event, t, lang)}
        body={eventSummary(event, t, lang)}
        aside={
          <div className="rounded-box border border-base-300 bg-base-200/60 p-4">
            <div className="flex flex-wrap gap-2">
              <SeverityBadge severity={event.severity} />
              <ConfirmationBadge state={event.confirmation_state} />
              <span className={`badge badge-sm ${relevance.className}`}>{relevance.label}</span>
            </div>
            <div className="mt-4 space-y-2 text-sm text-base-content/65">
              <p>
                <span className="font-semibold text-base-content">{t.detail.eventTime}</span>{" "}
                {formatFullTime(timestamp, lang, t)}
              </p>
              <p>
                <span className="font-semibold text-base-content">{t.detail.category}</span>{" "}
                {displayCategory(event.content_category, t)}
              </p>
            </div>
          </div>
        }
      />

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_320px] lg:px-8">
        <article className="rounded-box border border-base-300 bg-base-200/40 p-5">
          <h2 className="text-lg font-semibold">{t.detail.summaryTitle}</h2>
          <p className="mt-3 leading-7 text-base-content/75">{eventSummary(event, t, lang)}</p>
          <p className="mt-5 text-xs leading-5 text-base-content/50">
            {t.detail.boundary}
          </p>
        </article>

        <section className="rounded-box border border-base-300 bg-base-200/40 p-5 lg:col-start-1">
          <h2 className="text-lg font-semibold">{t.raw.supportingItems}</h2>
          <div className="mt-4 grid gap-3">
            {rawItemsQuery.isLoading && <LoadingState />}
            {rawItemsQuery.isError && <ErrorState message={(rawItemsQuery.error as Error).message} />}
            {rawItemsQuery.data?.items.length === 0 && (
              <p className="text-sm text-base-content/60">{t.raw.noSupportingItems}</p>
            )}
            {rawItemsQuery.data?.items.map((item) => (
              <RawItemCard key={item.id} item={item} compact showFullTranslation />
            ))}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-box border border-base-300 bg-base-200/40 p-4">
            <h3 className="text-sm font-semibold">{t.detail.sources}</h3>
            <div className="mt-3 grid gap-2 text-sm">
              {event.public_source_links.length === 0 && (
                <p className="text-base-content/60">{t.detail.noSources}</p>
              )}
              {event.public_source_links.map((source) => (
                <a
                  key={`${source.url}-${source.source_name ?? source.label ?? "source"}`}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  title={sourceBackground(source, t)}
                  aria-label={`${sourceLabel(source, t)}: ${sourceBackground(source, t)}`}
                  className="inline-flex items-center justify-between gap-3 rounded-field border border-base-300 px-3 py-2 text-base-content/70 hover:border-primary/50 hover:text-primary"
                >
                  <span>{sourceLabel(source, t)}</span>
                  <ExternalLink className="h-4 w-4" />
                </a>
              ))}
            </div>
          </section>

          <section className="rounded-box border border-base-300 bg-base-200/40 p-4">
            <h3 className="text-sm font-semibold">{t.detail.tagsActors}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {event.topic_tags.map((tag) => (
                <Link key={tag} to={to(`/tags/${encodeURIComponent(tag)}`)} className="badge badge-ghost font-mono">
                  #{tag}
                </Link>
              ))}
              {event.mentioned_actors.map((actor) => (
                <span key={actor} className="badge badge-outline">
                  {actor}
                </span>
              ))}
            </div>
          </section>
        </aside>
      </section>
    </>
  );
}
