import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import type { PublicEvent } from "../api/types";
import { useI18n, useLanguage, useLocalizedPath } from "../i18n";
import { ConfirmationBadge, SeverityBadge } from "./Badges";
import { displayCategory, eventSummary, eventTimestamp, eventTitle, formatTime, relevanceBand } from "./format";

export function EventCard({ event }: { event: PublicEvent }) {
  const lang = useLanguage();
  const t = useI18n();
  const to = useLocalizedPath();
  const relevance = relevanceBand(event.relevance_score, t);
  const timestamp = eventTimestamp(event);

  return (
    <article className="rounded-box border border-base-300 bg-base-200/40 p-4 transition-colors hover:border-primary/40 sm:p-5">
      <div className="flex flex-wrap items-center gap-2 text-xs text-base-content/60">
        <SeverityBadge severity={event.severity} />
        <ConfirmationBadge state={event.confirmation_state} />
        <span className={`badge badge-sm ${relevance.className}`}>{relevance.label}</span>
        <span className="font-mono">{formatTime(timestamp, lang, t)}</span>
      </div>

      <Link to={to(`/events/${event.id}`)} className="mt-4 block">
        <h2 className="text-lg font-semibold leading-7 text-base-content hover:text-primary">
          {eventTitle(event, t)}
        </h2>
      </Link>

      <p className="mt-2 text-sm leading-6 text-base-content/70">{eventSummary(event, t)}</p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="badge badge-outline badge-sm font-mono">{displayCategory(event.content_category, t)}</span>
        {event.topic_tags.slice(0, 6).map((tag) => (
          <Link key={tag} to={to(`/tags/${encodeURIComponent(tag)}`)} className="badge badge-ghost badge-sm font-mono">
            #{tag}
          </Link>
        ))}
      </div>

      {event.public_source_links.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-base-300/60 pt-4 text-xs">
          {event.public_source_links.slice(0, 4).map((source) => (
            <a
              key={`${source.url}-${source.source_name ?? source.label ?? "source"}`}
              href={source.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-base-content/60 hover:text-primary"
            >
              {source.source_name || source.label || t.detail.source}
              <ExternalLink className="h-3 w-3" />
            </a>
          ))}
        </div>
      )}
    </article>
  );
}
