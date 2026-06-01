import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { RawItem } from "../api/types";
import { OfficialBadge, PriorityBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime } from "../components/Format";
import { PageHeader } from "../components/Layout";

/** Heuristic: only offer collapse when content is long enough to be clamped. */
function isCollapsible(text: string): boolean {
  return text.length > 280 || text.split("\n").length > 6;
}

function MetaField({ label, tip, children }: { label: string; tip?: string; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1" title={tip}>
      <span className="text-[10px] font-medium uppercase tracking-wide text-base-content/40">{label}</span>
      {children}
    </span>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={`transition-transform ${open ? "rotate-180" : ""}`}
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function RawItemCard({ item }: { item: RawItem }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const summary = item.summary_zh || item.summary_en || item.text_clean || item.text_raw || "-";
  const fullTranslation = item.full_translation_zh || item.full_translation_en;
  const originalContent = item.text_clean || item.text_raw || "-";
  const title = item.title || item.source_name;
  const contentLabel = fullTranslation ? t("timeline.fullTranslation") : t("timeline.originalContent");
  const contentText = fullTranslation || originalContent;
  const collapsible = isCollapsible(contentText);

  return (
    <article className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-base-content/60">
        <span className="font-mono text-base-content/70">{formatTime(item.published_at || item.ingested_at)}</span>
        <span className="font-medium text-base-content">{item.source_name}</span>
        <MetaField label={t("timeline.meta.official")} tip={t("timeline.meta.officialTip")}>
          <OfficialBadge value={item.official_level} />
        </MetaField>
        <MetaField label={t("timeline.meta.priority")} tip={t("timeline.meta.priorityTip")}>
          <PriorityBadge value={item.priority} />
        </MetaField>
        <MetaField label={t("timeline.meta.group")} tip={t("timeline.meta.groupTip")}>
          <span className="rounded bg-base-200 px-2 py-0.5">{item.source_group}</span>
        </MetaField>
        <MetaField label={t("timeline.meta.translation")} tip={t("timeline.meta.translationTip")}>
          <span className="rounded bg-base-200 px-2 py-0.5">{item.translation_status || "pending"}</span>
        </MetaField>
      </div>
      {item.title ? <h2 className="mb-2 text-sm font-semibold text-base-content">{title}</h2> : null}
      <p className="mb-3 whitespace-pre-wrap text-sm leading-6 text-base-content/80">{summary}</p>
      <div className="mb-3 rounded border border-base-200 bg-base-200/30 p-3">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-base-content/60">{contentLabel}</span>
          {collapsible ? (
            <button
              type="button"
              className="btn btn-ghost btn-xs gap-1 text-base-content/60"
              aria-expanded={expanded}
              onClick={() => setExpanded((value) => !value)}
            >
              {expanded ? t("common.showLess") : t("common.showMore")}
              <ChevronIcon open={expanded} />
            </button>
          ) : null}
        </div>
        <p
          className={`whitespace-pre-wrap text-sm leading-6 text-base-content/75 ${
            collapsible && !expanded ? "line-clamp-6" : ""
          }`}
        >
          {contentText}
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
}

const SOURCE_TYPES = [
  { labelKey: "common.sourceType.all", value: "" },
  { labelKey: "common.sourceType.telegram", value: "telegram" },
  { labelKey: "common.sourceType.rss", value: "rss" },
  { labelKey: "common.sourceType.atom", value: "atom" },
  { labelKey: "common.sourceType.htmlPolling", value: "html_polling" }
] as const;

const PRIORITIES = ["P0", "P1", "P2", "P3"] as const;

export function Timeline() {
  const { t } = useTranslation();
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
      <PageHeader title={t("timeline.title")} description={t("timeline.description")} />
      <div className="mb-4 grid gap-2 md:grid-cols-[1fr_180px_220px_120px_220px]">
        <input className="input input-bordered input-sm" placeholder={t("common.keywordSearch")} value={q} onChange={(event) => setQ(event.target.value)} />
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
              {t(sourceTypeOption.labelKey)}
            </option>
          ))}
        </select>
        <select
          className="select select-bordered select-sm"
          value={sourceId}
          onChange={(event) => setSourceId(event.target.value)}
        >
          <option value="">{t("common.allSources")}</option>
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
          <option value="">{t("common.allPriorities")}</option>
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
            {t("timeline.empty")}
          </div>
        ) : null}
        {query.data?.items.map((item) => <RawItemCard key={item.id} item={item} />)}
      </div>
    </>
  );
}
