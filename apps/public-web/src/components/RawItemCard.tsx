import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import type { PublicRawItem } from "../api/types";
import { useI18n, useLanguage, useLocalizedPath } from "../i18n";
import {
  displayCategory,
  formatTime,
  rawItemFullTranslation,
  rawItemSourceLabel,
  rawItemSummary,
  rawItemTimestamp,
  rawItemTitle,
  relevanceBand
} from "./format";

export function RawItemCard({
  item,
  compact = false,
  showFullTranslation = false
}: {
  item: PublicRawItem;
  compact?: boolean;
  showFullTranslation?: boolean;
}) {
  const lang = useLanguage();
  const t = useI18n();
  const to = useLocalizedPath();
  const relevance = relevanceBand(item.relevance_score, t);
  const timestamp = rawItemTimestamp(item);
  const fullTranslation = rawItemFullTranslation(item, lang);

  return (
    <article className="rounded-box border border-base-300 bg-base-200/40 p-4 transition-colors hover:border-primary/40">
      <div className="flex flex-wrap items-center gap-2 text-xs text-base-content/60">
        <span className={`badge badge-sm ${relevance.className}`}>{relevance.label}</span>
        {item.source_type && <span className="badge badge-ghost badge-sm font-mono">{item.source_type}</span>}
        <span className="font-mono">{formatTime(timestamp, lang, t)}</span>
      </div>

      <Link to={to(`/raw/${item.id}`)} className="mt-3 block">
        <h2 className={`${compact ? "text-base" : "text-lg"} font-semibold leading-7 hover:text-primary`}>
          {rawItemTitle(item, t)}
        </h2>
      </Link>

      <p className="mt-2 text-sm leading-6 text-base-content/70">{rawItemSummary(item, t, lang)}</p>

      {showFullTranslation && fullTranslation && (
        <details className="mt-3 border-t border-base-300/60 pt-3">
          <summary className="cursor-pointer text-sm font-semibold text-base-content/75 hover:text-primary">
            {t.raw.fullTranslation}
          </summary>
          <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-base-content/70">
            {fullTranslation}
          </p>
        </details>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="badge badge-outline badge-sm font-mono">{displayCategory(item.content_category, t)}</span>
        {item.topic_tags.slice(0, compact ? 3 : 6).map((tag) => (
          <Link key={tag} to={to(`/raw`, `?tag=${encodeURIComponent(tag)}`)} className="badge badge-ghost badge-sm font-mono">
            #{tag}
          </Link>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-base-300/60 pt-4 text-xs">
        <span className="text-base-content/60">{rawItemSourceLabel(item, t)}</span>
        {item.source_url && (
          <a
            href={item.source_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-base-content/60 hover:text-primary"
          >
            {t.detail.source}
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </article>
  );
}
