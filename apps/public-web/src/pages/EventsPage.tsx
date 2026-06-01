import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCategories, listEvents, listTags, getOverviewStats } from "../api/client";
import type { EventFilters } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import { EventCard } from "../components/EventCard";
import { PageHeader } from "../components/PageHeader";
import { StatsStrip } from "../components/StatsStrip";

const pageSize = 20;

export function EventsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");

  const filters = useMemo<EventFilters>(
    () => ({
      severity: searchParams.get("severity") ?? undefined,
      confirmation_state: searchParams.get("confirmation_state") ?? undefined,
      tag: searchParams.get("tag") ?? undefined,
      category: searchParams.get("category") ?? undefined,
      q: searchParams.get("q") ?? undefined,
      page: Number(searchParams.get("page") ?? "1"),
      page_size: pageSize
    }),
    [searchParams]
  );

  const eventsQuery = useQuery({
    queryKey: ["public-events", filters],
    queryFn: () => listEvents(filters),
    refetchInterval: 60_000
  });
  const tagsQuery = useQuery({ queryKey: ["public-tags"], queryFn: listTags, staleTime: 60_000 });
  const categoriesQuery = useQuery({
    queryKey: ["public-categories"],
    queryFn: listCategories,
    staleTime: 60_000
  });
  const statsQuery = useQuery({ queryKey: ["public-stats"], queryFn: getOverviewStats, staleTime: 30_000 });

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set(key, value);
    } else {
      next.delete(key);
    }
    next.delete("page");
    setSearchParams(next);
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    updateFilter("q", query.trim());
  }

  function setPage(page: number) {
    const next = new URLSearchParams(searchParams);
    if (page <= 1) {
      next.delete("page");
    } else {
      next.set("page", String(page));
    }
    setSearchParams(next);
  }

  const totalPages = Math.max(1, Math.ceil((eventsQuery.data?.total ?? 0) / pageSize));
  const currentPage = Number(filters.page ?? 1);

  return (
    <>
      <PageHeader
        eyebrow="Public event radar"
        title="TickBase News"
        body={
          <>
            去敏後的公開事件流，聚焦 XAUUSD、Fed、Trump、Iran、IRGC、能源與地緣風險。
            內容用於追蹤消息與來源確認狀態，不提供交易建議。
          </>
        }
        aside={<StatsStrip stats={statsQuery.data} />}
      />

      <section className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="rounded-box border border-base-300 bg-base-200/40 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Filters
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1.1fr_repeat(4,minmax(0,0.7fr))]">
            <form onSubmit={submitSearch} className="join w-full">
              <label className="input join-item input-bordered flex min-w-0 flex-1 items-center gap-2">
                <Search className="h-4 w-4 text-base-content/40" />
                <input
                  className="min-w-0 grow"
                  placeholder="Search public summaries"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <button className="btn btn-primary join-item" type="submit" aria-label="Search">
                <Search className="h-4 w-4" />
              </button>
            </form>

            <select
              className="select select-bordered w-full"
              value={filters.severity ?? ""}
              onChange={(event) => updateFilter("severity", event.target.value)}
              aria-label="Severity"
            >
              <option value="">All severity</option>
              <option value="S">S</option>
              <option value="A">A</option>
              <option value="B">B</option>
              <option value="C">C</option>
            </select>

            <select
              className="select select-bordered w-full"
              value={filters.confirmation_state ?? ""}
              onChange={(event) => updateFilter("confirmation_state", event.target.value)}
              aria-label="Confirmation state"
            >
              <option value="">All confirmation</option>
              <option value="confirmed">confirmed</option>
              <option value="partially_confirmed">partially confirmed</option>
              <option value="unconfirmed">unconfirmed</option>
              <option value="contradicted">contradicted</option>
            </select>

            <select
              className="select select-bordered w-full"
              value={filters.category ?? ""}
              onChange={(event) => updateFilter("category", event.target.value)}
              aria-label="Category"
            >
              <option value="">All categories</option>
              {(categoriesQuery.data ?? []).map((item) => (
                <option key={item.category} value={item.category}>
                  {item.category} ({item.count})
                </option>
              ))}
            </select>

            <select
              className="select select-bordered w-full"
              value={filters.tag ?? ""}
              onChange={(event) => updateFilter("tag", event.target.value)}
              aria-label="Tag"
            >
              <option value="">All tags</option>
              {(tagsQuery.data ?? []).map((item) => (
                <option key={item.tag} value={item.tag}>
                  #{item.tag} ({item.count})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          {eventsQuery.isLoading && <LoadingState />}
          {eventsQuery.isError && <ErrorState message={(eventsQuery.error as Error).message} />}
          {eventsQuery.data?.items.length === 0 && (
            <EmptyState
              title="沒有符合條件的公開事件"
              body="請調整 severity、category、tag 或搜尋字串。公開網站只顯示已核准同步的 public-safe events。"
            />
          )}
          {eventsQuery.data?.items.map((event) => <EventCard key={event.id} event={event} />)}
        </div>

        {eventsQuery.data && eventsQuery.data.total > pageSize && (
          <div className="mt-6 flex flex-col items-center justify-between gap-3 sm:flex-row">
            <p className="text-sm text-base-content/60">
              Showing page {currentPage} of {totalPages}, {eventsQuery.data.total} public events.
            </p>
            <div className="join">
              <button
                className="btn join-item btn-sm"
                disabled={currentPage <= 1}
                onClick={() => setPage(currentPage - 1)}
                type="button"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <Link className="btn join-item btn-sm btn-ghost" to="/events">
                Reset
              </Link>
              <button
                className="btn join-item btn-sm"
                disabled={currentPage >= totalPages}
                onClick={() => setPage(currentPage + 1)}
                type="button"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
