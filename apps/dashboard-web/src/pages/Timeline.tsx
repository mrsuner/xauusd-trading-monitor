import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { OfficialBadge, PriorityBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime } from "../components/Format";
import { PageHeader } from "../components/Layout";

const SOURCE_TYPE_TABS = [
  { label: "Telegram", value: "telegram" },
  { label: "RSS", value: "rss" }
] as const;

export function Timeline() {
  const [q, setQ] = useState("");
  const [sourceGroup, setSourceGroup] = useState("");
  const [sourceType, setSourceType] = useState<(typeof SOURCE_TYPE_TABS)[number]["value"]>("telegram");
  const query = useQuery({
    queryKey: ["raw-items", q, sourceGroup, sourceType],
    queryFn: () => api.rawItems({ page_size: 75, q, source_group: sourceGroup, source_type: sourceType }),
    refetchInterval: 15000
  });

  return (
    <>
      <PageHeader title="Live Timeline" description="Recent raw items from Telegram, RSS and official pages." />
      <div className="tabs tabs-box mb-4 w-fit">
        {SOURCE_TYPE_TABS.map((tab) => (
          <button
            key={tab.value}
            className={`tab ${sourceType === tab.value ? "tab-active" : ""}`}
            type="button"
            onClick={() => setSourceType(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="mb-4 grid gap-2 md:grid-cols-[1fr_260px]">
        <input className="input input-bordered input-sm" placeholder="Keyword search" value={q} onChange={(event) => setQ(event.target.value)} />
        <input className="input input-bordered input-sm" placeholder="source_group" value={sourceGroup} onChange={(event) => setSourceGroup(event.target.value)} />
      </div>
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="space-y-3">
        {query.isLoading
          ? Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="rounded border border-base-300 bg-base-100 p-4">
              <div className="skeleton mb-3 h-4 w-48" />
              <div className="skeleton mb-2 h-5 w-3/4" />
              <div className="skeleton h-4 w-full" />
            </div>
          ))
          : null}
        {query.data?.items.length === 0 ? (
          <div className="rounded border border-base-300 bg-base-100 py-10 text-center text-base-content/50">
            No raw items in selected range.
          </div>
        ) : null}
        {query.data?.items.map((item) => {
          const messageBody = item.summary_zh || item.summary_en || item.text_clean || item.text_raw || "-";
          const title = item.title || item.source_name;

          return (
            <article key={item.id} className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-base-content/60">
                <span>{formatTime(item.published_at || item.ingested_at)}</span>
                <span className="font-medium text-base-content">{item.source_name}</span>
                <OfficialBadge value={item.official_level} />
                <PriorityBadge value={item.priority} />
                <span className="rounded bg-base-200 px-2 py-0.5">{item.source_group}</span>
                <span className="rounded bg-base-200 px-2 py-0.5">{item.translation_status || "pending"}</span>
              </div>
              {item.title ? <h2 className="mb-2 text-sm font-semibold text-base-content">{title}</h2> : null}
              <p className="mb-3 whitespace-pre-wrap text-sm leading-6 text-base-content/80">{messageBody}</p>
              <div className="grid gap-2 text-xs text-base-content/55 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                <div className="min-w-0">
                  <span className="mr-2 font-medium text-base-content/70">id</span>
                  <span className="break-all font-mono">{item.id}</span>
                </div>
                <div className="min-w-0">
                  <span className="mr-2 font-medium text-base-content/70">url</span>
                  {item.url ? (
                    <a className="link link-hover break-all" href={item.url} target="_blank" rel="noreferrer">
                      {item.url}
                    </a>
                  ) : (
                    <span>-</span>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </>
  );
}
