import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { listEvents } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import { EventCard } from "../components/EventCard";
import { PageHeader } from "../components/PageHeader";

export function TagPage() {
  const { tag } = useParams();
  const decodedTag = tag ? decodeURIComponent(tag) : "";
  const query = useQuery({
    queryKey: ["public-events-tag", decodedTag],
    queryFn: () => listEvents({ tag: decodedTag, page_size: 20 }),
    enabled: Boolean(decodedTag)
  });

  return (
    <>
      <PageHeader
        eyebrow="Topic tag"
        title={`#${decodedTag || "unknown"}`}
        body="依 topic tag 聚合的公開事件流。Tag 來自事件處理流程中的 public-safe taxonomy，用於檢索與分組。"
      />
      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="grid gap-4">
          {query.isLoading && <LoadingState />}
          {query.isError && <ErrorState message={(query.error as Error).message} />}
          {query.data?.items.length === 0 && (
            <EmptyState title="此 tag 尚無公開事件" body="後續同步事件時會自動出現在這裡。" />
          )}
          {query.data?.items.map((event) => <EventCard key={event.id} event={event} />)}
        </div>
      </section>
    </>
  );
}
