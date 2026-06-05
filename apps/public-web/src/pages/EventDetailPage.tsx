import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getEvent } from "../api/client";
import { ConfirmationBadge, SeverityBadge } from "../components/Badges";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import {
  displayCategory,
  eventSummary,
  eventTimestamp,
  eventTitle,
  formatFullTime,
  relevanceBand
} from "../components/format";
import { useLanguage, useLocalizedPath } from "../i18n";
import { PageHeader } from "../components/PageHeader";

export function EventDetailPage() {
  const { eventId } = useParams();
  const lang = useLanguage();
  const to = useLocalizedPath();
  const query = useQuery({
    queryKey: ["public-event", eventId, lang],
    queryFn: () => getEvent(eventId ?? "", lang),
    enabled: Boolean(eventId)
  });

  if (!eventId) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <EmptyState title="Event id is missing" body="請回到事件列表重新開啟公開事件。" />
      </section>
    );
  }

  if (query.isLoading) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <LoadingState label="Loading event detail..." />
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
        <EmptyState title="Event not found" body="這筆公開事件不存在，或已被隱藏。" />
      </section>
    );
  }

  const relevance = relevanceBand(event.relevance_score);
  const timestamp = eventTimestamp(event);

  return (
    <>
      <PageHeader
        eyebrow="Public event detail"
        title={eventTitle(event)}
        body={eventSummary(event)}
        aside={
          <div className="rounded-box border border-base-300 bg-base-200/60 p-4">
            <div className="flex flex-wrap gap-2">
              <SeverityBadge severity={event.severity} />
              <ConfirmationBadge state={event.confirmation_state} />
              <span className={`badge badge-sm ${relevance.className}`}>{relevance.label}</span>
            </div>
            <div className="mt-4 space-y-2 text-sm text-base-content/65">
              <p>
                <span className="font-semibold text-base-content">Event time:</span>{" "}
                {formatFullTime(timestamp)}
              </p>
              <p>
                <span className="font-semibold text-base-content">Category:</span>{" "}
                {displayCategory(event.content_category)}
              </p>
            </div>
          </div>
        }
      />

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_320px] lg:px-8">
        <article className="rounded-box border border-base-300 bg-base-200/40 p-5">
          <h2 className="text-lg font-semibold">Public Summary</h2>
          <p className="mt-3 leading-7 text-base-content/75">{eventSummary(event)}</p>
          <p className="mt-5 text-xs leading-5 text-base-content/50">
            This page only includes public-safe summaries and source attribution. It does not include
            raw item text, private delivery state, prompts, or model usage data.
          </p>
        </article>

        <aside className="space-y-4">
          <section className="rounded-box border border-base-300 bg-base-200/40 p-4">
            <h3 className="text-sm font-semibold">Sources</h3>
            <div className="mt-3 grid gap-2 text-sm">
              {event.public_source_links.length === 0 && (
                <p className="text-base-content/60">No public source links available.</p>
              )}
              {event.public_source_links.map((source) => (
                <a
                  key={`${source.url}-${source.source_name ?? source.label ?? "source"}`}
                  href={source.url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-between gap-3 rounded-field border border-base-300 px-3 py-2 text-base-content/70 hover:border-primary/50 hover:text-primary"
                >
                  <span>{source.source_name || source.label || "Source"}</span>
                  <ExternalLink className="h-4 w-4" />
                </a>
              ))}
            </div>
          </section>

          <section className="rounded-box border border-base-300 bg-base-200/40 p-4">
            <h3 className="text-sm font-semibold">Tags & Actors</h3>
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
