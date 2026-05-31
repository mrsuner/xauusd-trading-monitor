import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { OfficialBadge, PriorityBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime } from "../components/Format";
import { PageHeader } from "../components/Layout";

const SOURCE_TYPES = [
  { label: "All source types", value: "" },
  { label: "Telegram", value: "telegram" },
  { label: "RSS", value: "rss" },
  { label: "Atom", value: "atom" },
  { label: "HTML polling", value: "html_polling" }
] as const;

const PRIORITIES = ["P0", "P1", "P2", "P3"] as const;

export function Timeline() {
  const [q, setQ] = useState("");
  const [sourceGroup, setSourceGroup] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [priority, setPriority] = useState("");
  const sources = useQuery({
    queryKey: ["timeline-sources", sourceType, priority],
    queryFn: () => api.sources({ page_size: 200, source_type: sourceType, priority })
  });
  const query = useQuery({
    queryKey: ["raw-items", q, sourceGroup, sourceType, sourceId, priority],
    queryFn: () =>
      api.rawItems({
        page_size: 75,
        q,
        source_group: sourceGroup,
        source_type: sourceType,
        source_id: sourceId,
        priority
      }),
    refetchInterval: 15000
  });

  return (
    <>
      <PageHeader title="Live Timeline" description="Recent raw items from Telegram, RSS and official pages." />
      <div className="mb-4 grid gap-2 md:grid-cols-[1fr_180px_220px_120px_220px]">
        <input className="input input-bordered input-sm" placeholder="Keyword search" value={q} onChange={(event) => setQ(event.target.value)} />
        <select
          className="select select-bordered select-sm"
          value={sourceType}
          onChange={(event) => {
            setSourceType(event.target.value);
            setSourceId("");
          }}
        >
          {SOURCE_TYPES.map((sourceTypeOption) => (
            <option key={sourceTypeOption.value} value={sourceTypeOption.value}>
              {sourceTypeOption.label}
            </option>
          ))}
        </select>
        <select
          className="select select-bordered select-sm"
          value={sourceId}
          onChange={(event) => setSourceId(event.target.value)}
        >
          <option value="">All sources</option>
          {sources.data?.items.map((source) => (
            <option key={source.id} value={source.id}>
              {source.name}
            </option>
          ))}
        </select>
        <select
          className="select select-bordered select-sm"
          value={priority}
          onChange={(event) => {
            setPriority(event.target.value);
            setSourceId("");
          }}
        >
          <option value="">All priorities</option>
          {PRIORITIES.map((priorityOption) => (
            <option key={priorityOption} value={priorityOption}>
              {priorityOption}
            </option>
          ))}
        </select>
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
          const summary = item.summary_zh || item.summary_en || item.text_clean || item.text_raw || "-";
          const fullTranslation = item.full_translation_zh || item.full_translation_en;
          const originalContent = item.text_clean || item.text_raw || "-";
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
              <p className="mb-3 whitespace-pre-wrap text-sm leading-6 text-base-content/80">{summary}</p>
              <div className="mb-3 rounded border border-base-200 bg-base-200/30 p-3">
                <div className="mb-1 text-xs font-medium text-base-content/60">
                  {fullTranslation ? "Full translation" : "Original content"}
                </div>
                <p className="line-clamp-6 whitespace-pre-wrap text-sm leading-6 text-base-content/75">
                  {fullTranslation || originalContent}
                </p>
              </div>
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
