import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getRawItem } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import {
  displayCategory,
  formatFullTime,
  rawItemFullTranslation,
  rawItemSourceLabel,
  rawItemSummary,
  rawItemTimestamp,
  rawItemTitle,
  relevanceBand
} from "../components/format";
import { PageHeader } from "../components/PageHeader";
import { useI18n, useLanguage, useLocalizedPath } from "../i18n";

export function RawItemDetailPage() {
  const { rawItemId } = useParams();
  const lang = useLanguage();
  const t = useI18n();
  const to = useLocalizedPath();
  const query = useQuery({
    queryKey: ["public-raw-item", rawItemId, lang],
    queryFn: () => getRawItem(rawItemId ?? "", lang),
    enabled: Boolean(rawItemId)
  });

  if (!rawItemId) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <EmptyState title={t.raw.emptyTitle} body={t.raw.emptyBody} />
      </section>
    );
  }

  if (query.isLoading) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <LoadingState />
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

  const item = query.data;
  if (!item) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <EmptyState title={t.raw.emptyTitle} body={t.raw.emptyBody} />
      </section>
    );
  }

  const relevance = relevanceBand(item.relevance_score, t);
  const timestamp = rawItemTimestamp(item);
  const fullTranslation = rawItemFullTranslation(item, lang);

  return (
    <>
      <PageHeader
        eyebrow={t.raw.eyebrow}
        title={rawItemTitle(item, t)}
        body={rawItemSummary(item, t, lang)}
        aside={
          <div className="rounded-box border border-base-300 bg-base-200/60 p-4">
            <div className="flex flex-wrap gap-2">
              <span className={`badge badge-sm ${relevance.className}`}>{relevance.label}</span>
              {item.source_type && <span className="badge badge-ghost badge-sm font-mono">{item.source_type}</span>}
            </div>
            <div className="mt-4 space-y-2 text-sm text-base-content/65">
              <p>
                <span className="font-semibold text-base-content">{t.detail.eventTime}</span>{" "}
                {formatFullTime(timestamp, lang, t)}
              </p>
              <p>
                <span className="font-semibold text-base-content">{t.detail.category}</span>{" "}
                {displayCategory(item.content_category, t)}
              </p>
            </div>
          </div>
        }
      />

      <section className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_320px] lg:px-8">
        <article className="space-y-4">
          <TextPanel title={t.raw.summary} body={rawItemSummary(item, t, lang)} />
          <TextPanel title={t.raw.originalContent} body={item.original_content || t.raw.noOriginalContent} />
          <TextPanel title={t.raw.fullTranslation} body={fullTranslation || t.raw.noFullTranslation} />
        </article>

        <aside className="space-y-4">
          <section className="rounded-box border border-base-300 bg-base-200/40 p-4">
            <h3 className="text-sm font-semibold">{t.detail.sources}</h3>
            <div className="mt-3 grid gap-2 text-sm">
              <div className="rounded-field border border-base-300 px-3 py-2 text-base-content/70">
                {rawItemSourceLabel(item, t)}
              </div>
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-between gap-3 rounded-field border border-base-300 px-3 py-2 text-base-content/70 hover:border-primary/50 hover:text-primary"
                >
                  <span>{t.detail.source}</span>
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </div>
          </section>

          <section className="rounded-box border border-base-300 bg-base-200/40 p-4">
            <h3 className="text-sm font-semibold">{t.detail.tagsActors}</h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {item.topic_tags.map((tag) => (
                <Link key={tag} to={to("/raw", `?tag=${encodeURIComponent(tag)}`)} className="badge badge-ghost font-mono">
                  #{tag}
                </Link>
              ))}
              {item.mentioned_actors.map((actor) => (
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

function TextPanel({ title, body }: { title: string; body: string }) {
  return (
    <section className="rounded-box border border-base-300 bg-base-200/40 p-5">
      <h2 className="text-base font-semibold">{title}</h2>
      <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-base-content/75">{body}</p>
    </section>
  );
}
