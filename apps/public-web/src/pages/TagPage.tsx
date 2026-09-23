import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { listEvents } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import { EventCard } from "../components/EventCard";
import { PageHeader } from "../components/PageHeader";
import { useI18n } from "../i18n";
import { useAppliedReaderPreferences } from "../features/reader-preferences/domain/useAppliedReaderPreferences";

export function TagPage() {
  const { tag } = useParams();
  const reader = useAppliedReaderPreferences();
  const t = useI18n();
  const decodedTag = tag ? decodeURIComponent(tag) : "";
  const query = useQuery({
    queryKey: ["public-events-tag", decodedTag, reader.contentLanguage, reader.minSeverity],
    queryFn: () => listEvents({ tag: decodedTag, lang: reader.contentLanguage, min_severity: reader.minSeverity, page_size: 20 }),
    enabled: Boolean(decodedTag) && reader.ready
  });

  return (
    <>
      <PageHeader
        eyebrow={t.tag.eyebrow}
        title={`#${decodedTag || t.tag.fallbackTitle}`}
        body={t.tag.body}
      />
      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-4">
          {(!reader.ready || query.isLoading) && <LoadingState />}
          {query.isError && <ErrorState message={(query.error as Error).message} />}
          {query.data?.items.length === 0 && (
            <EmptyState title={t.tag.emptyTitle} body={t.tag.emptyBody} />
          )}
          {query.data?.items.map((event) => <EventCard key={event.id} event={event} contentLanguage={reader.contentLanguage} />)}
        </div>
      </section>
    </>
  );
}
