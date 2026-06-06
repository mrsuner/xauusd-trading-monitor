import { type ReactNode, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ContentCategory, RawItem, TagOption } from "../api/types";
import { OfficialBadge, PriorityBadge, StatusBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime, Score } from "../components/Format";
import { PageHeader } from "../components/Layout";
import { rawItemDisplaySummary, rawItemFullTranslation, rawItemOriginalContent } from "../utils/rawItemTranslations";

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

function relevanceTone(item: RawItem): { labelKey: string; className: string } {
  if (item.has_event) return { labelKey: "timeline.relevance.hasEvent", className: "badge-error" };
  if (item.is_relevant === false) return { labelKey: "timeline.relevance.filtered", className: "badge-ghost" };
  if (item.relevance_score === undefined || item.relevance_score === null) {
    return { labelKey: "timeline.relevance.pending", className: "badge-ghost" };
  }
  if (item.relevance_score >= 70) return { labelKey: "timeline.relevance.high", className: "badge-warning" };
  if (item.relevance_score >= 30) return { labelKey: "timeline.relevance.medium", className: "badge-info" };
  return { labelKey: "timeline.relevance.low", className: "badge-outline" };
}

function cardTone(item: RawItem): string {
  if (item.event_severity === "S" || item.event_severity === "A") return "border-l-4 border-l-error";
  if (item.has_event) return "border-l-4 border-l-warning";
  if ((item.relevance_score ?? 0) >= 70) return "border-l-4 border-l-info";
  if (item.is_relevant === false) return "opacity-75";
  return "";
}

type RawItemCardProps = {
  item: RawItem;
  categoryByKey: Map<string, ContentCategory>;
  tagByKey: Map<string, TagOption>;
  onCategoryClick: (category: string) => void;
  onTagClick: (tag: string) => void;
  onActorClick: (actor: string) => void;
};

function RawItemCard({ item, categoryByKey, tagByKey, onCategoryClick, onTagClick, onActorClick }: RawItemCardProps) {
  const { i18n, t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const summary = rawItemDisplaySummary(item, i18n.language);
  const fullTranslation = rawItemFullTranslation(item, i18n.language);
  const originalContent = rawItemOriginalContent(item) || "-";
  const title = item.title || item.source_name;
  const contentLabel = fullTranslation ? t("timeline.fullTranslation") : t("timeline.originalContent");
  const contentText = fullTranslation || originalContent;
  const collapsible = isCollapsible(contentText);
  const tags = item.topic_tags ?? [];
  const actors = item.mentioned_actors ?? [];
  const category = item.content_category ? categoryByKey.get(item.content_category) : undefined;
  const categoryLabel = category
    ? i18n.language.startsWith("zh")
      ? category.label_zh
      : category.label_en
    : item.content_category;
  const relevance = relevanceTone(item);

  return (
    <article className={`rounded border border-base-300 bg-base-100 p-4 shadow-sm ${cardTone(item)}`}>
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
        <MetaField label={t("timeline.meta.classification")} tip={t("timeline.meta.classificationTip")}>
          <StatusBadge value={item.classification_status || "pending"} />
        </MetaField>
        <MetaField label={t("timeline.meta.relevance")} tip={t("timeline.meta.relevanceTip")}>
          <span className={`badge badge-sm ${relevance.className}`}>
            {t(relevance.labelKey)} <Score value={item.relevance_score} />
          </span>
        </MetaField>
        {item.has_event ? (
          <MetaField label={t("timeline.meta.event")} tip={t("timeline.meta.eventTip")}>
            <Link className="badge badge-sm badge-outline gap-1 hover:badge-primary" to={`/events/${item.event_id}`}>
              {t("timeline.viewEvent")} {item.event_severity ?? "-"}
            </Link>
          </MetaField>
        ) : null}
        {item.content_category ? (
          <MetaField label={t("timeline.meta.category")} tip={t("timeline.meta.categoryTip")}>
            <button
              type="button"
              className="rounded bg-info/10 px-2 py-0.5 text-info-content transition hover:bg-info/20"
              title={category?.description ?? item.content_category}
              onClick={() => onCategoryClick(item.content_category ?? "")}
            >
              {categoryLabel}
            </button>
          </MetaField>
        ) : null}
      </div>
      {item.filter_reason ? (
        <div className="mb-3 rounded border border-base-300 bg-base-200/40 px-3 py-2 text-xs text-base-content/65">
          <span className="mr-2 font-medium text-base-content/75">{t("timeline.filterReason")}</span>
          {item.filter_reason}
        </div>
      ) : null}
      {item.title ? <h2 className="mb-2 text-sm font-semibold text-base-content">{title}</h2> : null}
      <p className="mb-3 whitespace-pre-wrap text-sm leading-6 text-base-content/80">{summary}</p>
      {tags.length || actors.length ? (
        <div className="mb-3 flex flex-wrap gap-1.5 text-xs">
          {tags.slice(0, 8).map((tag) => {
            const tagOption = tagByKey.get(tag);
            return (
              <button
                key={`tag-${tag}`}
                type="button"
                className="rounded bg-base-200 px-2 py-0.5 text-base-content/65 transition hover:bg-base-300 hover:text-base-content"
                title={tagOption?.label ?? tag}
                onClick={() => onTagClick(tag)}
              >
                #{tag}
              </button>
            );
          })}
          {actors.slice(0, 6).map((actor) => (
            <button
              key={`actor-${actor}`}
              type="button"
              className="rounded border border-base-300 px-2 py-0.5 text-base-content/65 transition hover:border-base-content/30 hover:text-base-content"
              onClick={() => onActorClick(actor)}
            >
              {actor}
            </button>
          ))}
        </div>
      ) : null}
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
const RELEVANCE_MODES = [
  { labelKey: "timeline.filter.allRelevance", value: "" },
  { labelKey: "timeline.filter.relevantOnly", value: "relevant" },
  { labelKey: "timeline.filter.filteredOnly", value: "filtered" },
  { labelKey: "timeline.filter.hasEvent", value: "has_event" },
  { labelKey: "timeline.filter.pendingClassification", value: "pending" }
] as const;
const MIN_RELEVANCE_SCORES = ["", "30", "50", "70", "85"] as const;
export function Timeline() {
  const { i18n, t } = useTranslation();
  const [q, setQ] = useState("");
  const [sourceGroup, setSourceGroup] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [priority, setPriority] = useState("");
  const [contentCategory, setContentCategory] = useState("");
  const [topicTag, setTopicTag] = useState("");
  const [actor, setActor] = useState("");
  const [relevanceMode, setRelevanceMode] = useState("");
  const [minRelevanceScore, setMinRelevanceScore] = useState("");
  const relevanceParams = useMemo(
    () => ({
      is_relevant: relevanceMode === "relevant" ? true : relevanceMode === "filtered" ? false : undefined,
      has_event: relevanceMode === "has_event" ? true : undefined,
      classification_status: relevanceMode === "pending" ? "pending" : undefined,
      min_relevance_score: minRelevanceScore
    }),
    [minRelevanceScore, relevanceMode]
  );
  const sources = useQuery({
    queryKey: ["timeline-sources", sourceType, priority],
    queryFn: () => api.sources({ page_size: 200, source_type: sourceType, priority })
  });
  const filterOptions = useQuery({
    queryKey: ["raw-item-filters"],
    queryFn: () => api.rawItemFilters(),
    staleTime: 60000
  });
  const categories = useQuery({
    queryKey: ["taxonomy-categories"],
    queryFn: () => api.taxonomyCategories(),
    staleTime: 300000
  });
  const tags = useQuery({
    queryKey: ["taxonomy-tags"],
    queryFn: () => api.taxonomyTags(),
    staleTime: 300000
  });
  const query = useQuery({
    queryKey: [
      "raw-items",
      q,
      sourceGroup,
      sourceType,
      sourceId,
      priority,
      contentCategory,
      topicTag,
      actor,
      relevanceMode,
      minRelevanceScore
    ],
    queryFn: () =>
      api.rawItems({
        page_size: 75,
        q,
        source_group: sourceGroup,
        source_type: sourceType,
        source_id: sourceId,
        priority,
        content_category: contentCategory,
        topic_tag: topicTag,
        actor,
        ...relevanceParams
      }),
    refetchInterval: 15000
  });
  const categoryByKey = useMemo(
    () => new Map((categories.data?.items ?? []).map((category) => [category.key, category])),
    [categories.data?.items]
  );
  const tagByKey = useMemo(() => new Map((tags.data?.items ?? []).map((tag) => [tag.key, tag])), [tags.data?.items]);

  return (
    <>
      <PageHeader title={t("timeline.title")} description={t("timeline.description")} />
      <div className="mb-4 grid gap-2 md:grid-cols-2 xl:grid-cols-[minmax(180px,1fr)_150px_220px_110px_170px_170px_170px_160px_150px_180px]">
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
        <select
          className="select select-bordered select-sm"
          value={contentCategory}
          onChange={(event) => setContentCategory(event.target.value)}
        >
          <option value="">{t("timeline.filter.allCategories")}</option>
          {categories.data?.items.map((category) => (
            <option key={category.key} value={category.key}>
              {i18n.language.startsWith("zh") ? category.label_zh : category.label_en}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={topicTag} onChange={(event) => setTopicTag(event.target.value)}>
          <option value="">{t("timeline.filter.allTopics")}</option>
          {tags.data?.items.slice(0, 200).map((tag) => (
            <option key={tag.key} value={tag.key}>
              #{tag.key}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={actor} onChange={(event) => setActor(event.target.value)}>
          <option value="">{t("timeline.filter.allActors")}</option>
          {filterOptions.data?.mentioned_actors.slice(0, 200).map((actorOption) => (
            <option key={actorOption} value={actorOption}>
              {actorOption}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={relevanceMode} onChange={(event) => setRelevanceMode(event.target.value)}>
          {RELEVANCE_MODES.map((mode) => (
            <option key={mode.value} value={mode.value}>
              {t(mode.labelKey)}
            </option>
          ))}
        </select>
        <select
          className="select select-bordered select-sm"
          value={minRelevanceScore}
          onChange={(event) => setMinRelevanceScore(event.target.value)}
        >
          <option value="">{t("timeline.filter.anyScore")}</option>
          {MIN_RELEVANCE_SCORES.filter(Boolean).map((score) => (
            <option key={score} value={score}>
              {t("timeline.filter.minScore", { score })}
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
        {query.data?.items.map((item) => (
          <RawItemCard
            key={item.id}
            item={item}
            categoryByKey={categoryByKey}
            tagByKey={tagByKey}
            onCategoryClick={setContentCategory}
            onTagClick={setTopicTag}
            onActorClick={setActor}
          />
        ))}
      </div>
    </>
  );
}
