import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { listCategories, listRawItems, listTags } from "../api/client";
import type { RawItemFilters } from "../api/types";
import { EmptyState, ErrorState, LoadingState } from "../components/DataState";
import { PageHeader } from "../components/PageHeader";
import { RawItemCard } from "../components/RawItemCard";
import { useI18n, useLanguage, useLocalizedPath } from "../i18n";

const pageSize = 20;
const sourceTypes = ["telegram", "rss", "atom", "html_polling", "api"];

export function RawItemsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const lang = useLanguage();
  const t = useI18n();
  const to = useLocalizedPath();

  const filters = useMemo<RawItemFilters>(
    () => ({
      source_type: searchParams.get("source_type") ?? undefined,
      tag: searchParams.get("tag") ?? undefined,
      category: searchParams.get("category") ?? undefined,
      q: searchParams.get("q") ?? undefined,
      lang,
      page: Number(searchParams.get("page") ?? "1"),
      page_size: pageSize
    }),
    [lang, searchParams]
  );

  const rawItemsQuery = useQuery({
    queryKey: ["public-raw-items", filters],
    queryFn: () => listRawItems(filters),
    refetchInterval: 60_000
  });
  const tagsQuery = useQuery({ queryKey: ["public-tags"], queryFn: listTags, staleTime: 60_000 });
  const categoriesQuery = useQuery({
    queryKey: ["public-categories"],
    queryFn: listCategories,
    staleTime: 60_000
  });

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

  const totalPages = Math.max(1, Math.ceil((rawItemsQuery.data?.total ?? 0) / pageSize));
  const currentPage = Number(filters.page ?? 1);

  return (
    <>
      <PageHeader eyebrow={t.raw.eyebrow} title={t.raw.title} body={t.raw.body} />

      <section className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <div className="rounded-box border border-base-300 bg-base-200/40 p-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            {t.raw.filters}
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-[1.1fr_repeat(3,minmax(0,0.7fr))]">
            <form onSubmit={submitSearch} className="join w-full">
              <label className="input join-item input-bordered flex min-w-0 flex-1 items-center gap-2">
                <Search className="h-4 w-4 text-base-content/40" />
                <input
                  className="min-w-0 grow"
                  placeholder={t.raw.searchPlaceholder}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <button className="btn btn-primary join-item" type="submit" aria-label={t.raw.search}>
                <Search className="h-4 w-4" />
              </button>
            </form>

            <select
              className="select select-bordered w-full"
              value={filters.source_type ?? ""}
              onChange={(event) => updateFilter("source_type", event.target.value)}
              aria-label={t.raw.ariaSourceType}
            >
              <option value="">{t.raw.allSourceTypes}</option>
              {sourceTypes.map((sourceType) => (
                <option key={sourceType} value={sourceType}>
                  {sourceType}
                </option>
              ))}
            </select>

            <select
              className="select select-bordered w-full"
              value={filters.category ?? ""}
              onChange={(event) => updateFilter("category", event.target.value)}
              aria-label={t.raw.ariaCategory}
            >
              <option value="">{t.raw.allCategories}</option>
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
              aria-label={t.raw.ariaTag}
            >
              <option value="">{t.raw.allTags}</option>
              {(tagsQuery.data ?? []).map((item) => (
                <option key={item.tag} value={item.tag}>
                  #{item.tag} ({item.count})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          {rawItemsQuery.isLoading && <LoadingState />}
          {rawItemsQuery.isError && <ErrorState message={(rawItemsQuery.error as Error).message} />}
          {rawItemsQuery.data?.items.length === 0 && (
            <EmptyState title={t.raw.emptyTitle} body={t.raw.emptyBody} />
          )}
          {rawItemsQuery.data?.items.map((item) => <RawItemCard key={item.id} item={item} />)}
        </div>

        {rawItemsQuery.data && rawItemsQuery.data.total > pageSize && (
          <div className="mt-6 flex flex-col items-center justify-between gap-3 sm:flex-row">
            <p className="text-sm text-base-content/60">
              {t.raw.pageStatus(currentPage, totalPages, rawItemsQuery.data.total)}
            </p>
            <div className="join">
              <button
                className="btn join-item btn-sm"
                disabled={currentPage <= 1}
                onClick={() => setPage(currentPage - 1)}
                type="button"
                aria-label={t.raw.previousPage}
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <Link className="btn join-item btn-sm btn-ghost" to={to("/raw")}>
                {t.raw.reset}
              </Link>
              <button
                className="btn join-item btn-sm"
                disabled={currentPage >= totalPages}
                onClick={() => setPage(currentPage + 1)}
                type="button"
                aria-label={t.raw.nextPage}
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
