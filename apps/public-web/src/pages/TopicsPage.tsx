import { useQuery } from "@tanstack/react-query";
import { Hash } from "lucide-react";
import { Link } from "react-router-dom";
import { listTags } from "../api/client";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import { PageHeader } from "../components/PageHeader";
import { useI18n, useLocalizedPath } from "../i18n";

export function TopicsPage() {
  const t = useI18n().topics;
  const to = useLocalizedPath();
  const query = useQuery({
    queryKey: ["public-tags"],
    queryFn: listTags,
    staleTime: 60_000
  });

  return (
    <>
      <PageHeader eyebrow={t.eyebrow} title={t.title} body={t.body} />
      <section className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {query.isLoading && <LoadingState label={t.loading} />}
        {query.isError && <ErrorState message={(query.error as Error).message} />}
        {query.data?.length === 0 && <EmptyState title={t.emptyTitle} body={t.emptyBody} />}
        {query.data && query.data.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {query.data.map((item) => (
              <Link
                key={item.tag}
                className="group flex items-center justify-between gap-4 rounded-box border border-base-300 bg-base-200/45 p-4 transition-colors hover:border-primary/45 hover:bg-base-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                to={to(`/tags/${encodeURIComponent(item.tag)}`)}
              >
                <span className="flex min-w-0 items-center gap-3 font-medium">
                  <Hash className="h-4 w-4 shrink-0 text-primary" />
                  <span className="truncate">{item.tag}</span>
                </span>
                <span className="text-sm tabular-nums text-base-content/50">
                  {t.eventCount(item.count)}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
