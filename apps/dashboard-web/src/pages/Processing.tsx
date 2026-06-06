import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { OfficialBadge, PriorityBadge, StatusBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime, Score } from "../components/Format";
import { PageHeader } from "../components/Layout";
import { rawItemSummary } from "../utils/rawItemTranslations";

const SOURCE_TYPES = [
  { labelKey: "common.sourceType.all", value: "" },
  { labelKey: "common.sourceType.telegram", value: "telegram" },
  { labelKey: "common.sourceType.rss", value: "rss" },
  { labelKey: "common.sourceType.atom", value: "atom" },
  { labelKey: "common.sourceType.htmlPolling", value: "html_polling" }
] as const;

const PRIORITIES = ["P0", "P1", "P2", "P3"] as const;
const TRANSLATION_STATUSES = ["pending", "completed", "completed_truncated", "partial_completed", "skipped", "failed"] as const;
const CLASSIFICATION_STATUSES = ["pending", "running", "completed", "skipped", "failed", "retry"] as const;
const CLASSIFICATION_STAGES = ["normalize", "prefilter", "classify", "event_create", "completed"] as const;

function modelLabel(provider?: string | null, model?: string | null) {
  if (provider && model) return `${provider} / ${model}`;
  return model || provider || "-";
}

function formatCompactNumber(value?: number | null) {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatUsd(value?: string | number | null) {
  return `$${Number(value || 0).toFixed(6)}`;
}

function LayerBlock({
  title,
  status,
  model,
  updatedAt,
  error,
  children
}: {
  title: string;
  status?: string | null;
  model?: string | null;
  updatedAt?: string | null;
  error?: string | null;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <section className="rounded border border-base-300 bg-base-200/25 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-base-content/60">{title}</h3>
        <StatusBadge value={status} />
      </div>
      <div className="grid gap-1 text-xs text-base-content/65">
        <div>
          <span className="mr-2 font-medium text-base-content/75">{t("processing.field.model")}</span>
          <span className="break-all">{model || "-"}</span>
        </div>
        <div>
          <span className="mr-2 font-medium text-base-content/75">{t("processing.field.updated")}</span>
          <span>{formatTime(updatedAt)}</span>
        </div>
        {children}
      </div>
      {error ? <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-error">{error}</p> : null}
    </section>
  );
}

function UsageRow({
  callCount,
  totalTokens,
  inputTokens,
  outputTokens,
  cost
}: {
  callCount?: number | null;
  totalTokens?: number | null;
  inputTokens?: number | null;
  outputTokens?: number | null;
  cost?: string | number | null;
}) {
  const { t } = useTranslation();
  return (
    <>
      <div>
        <span className="mr-2 font-medium text-base-content/75">{t("processing.field.aiCalls")}</span>
        <span>{callCount ?? 0}</span>
      </div>
      <div>
        <span className="mr-2 font-medium text-base-content/75">{t("processing.field.tokens")}</span>
        <span>
          {formatCompactNumber(totalTokens)}{" "}
          <span className="text-base-content/50">
            {t("processing.field.tokensInOut", { in: formatCompactNumber(inputTokens), out: formatCompactNumber(outputTokens) })}
          </span>
        </span>
      </div>
      <div>
        <span className="mr-2 font-medium text-base-content/75">{t("processing.field.cost")}</span>
        <span>{formatUsd(cost)}</span>
      </div>
    </>
  );
}

export function Processing() {
  const { i18n, t } = useTranslation();
  const [q, setQ] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [sourceGroup, setSourceGroup] = useState("");
  const [priority, setPriority] = useState("");
  const [translationStatus, setTranslationStatus] = useState("");
  const [classificationStatus, setClassificationStatus] = useState("");
  const [classificationStage, setClassificationStage] = useState("");
  const [isRelevant, setIsRelevant] = useState("");

  const sources = useQuery({
    queryKey: ["processing-sources", sourceType, priority],
    queryFn: () => api.sources({ page_size: 200, source_type: sourceType, priority })
  });

  const query = useQuery({
    queryKey: [
      "processing-pipeline",
      q,
      sourceType,
      sourceId,
      sourceGroup,
      priority,
      translationStatus,
      classificationStatus,
      classificationStage,
      isRelevant
    ],
    queryFn: () =>
      api.processingPipeline({
        page_size: 75,
        q,
        source_type: sourceType,
        source_id: sourceId,
        source_group: sourceGroup,
        priority,
        translation_status: translationStatus,
        classification_status: classificationStatus,
        classification_stage: classificationStage,
        is_relevant: isRelevant
      }),
    refetchInterval: 15000
  });

  const aiUsage = useQuery({
    queryKey: ["ai-usage", 24],
    queryFn: () => api.aiUsage({ hours: 24 }),
    refetchInterval: 30000
  });

  return (
    <>
      <PageHeader title={t("processing.title")} description={t("processing.description")} />

      <section className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
          <div className="text-xs uppercase text-base-content/50">{t("processing.stat.aiCalls")}</div>
          <div className="mt-1 text-2xl font-semibold">{aiUsage.data?.totals.call_count ?? 0}</div>
          <div className="mt-1 text-xs text-base-content/55">{t("processing.stat.failed", { count: aiUsage.data?.totals.failure_count ?? 0 })}</div>
        </div>
        <div className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
          <div className="text-xs uppercase text-base-content/50">{t("processing.stat.tokens")}</div>
          <div className="mt-1 text-2xl font-semibold">{formatCompactNumber(aiUsage.data?.totals.total_tokens)}</div>
          <div className="mt-1 text-xs text-base-content/55">
            {t("processing.stat.tokensInOut", { in: formatCompactNumber(aiUsage.data?.totals.input_tokens), out: formatCompactNumber(aiUsage.data?.totals.output_tokens) })}
          </div>
        </div>
        <div className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
          <div className="text-xs uppercase text-base-content/50">{t("processing.stat.estCost")}</div>
          <div className="mt-1 text-2xl font-semibold">{formatUsd(aiUsage.data?.totals.estimated_cost_usd)}</div>
          <div className="mt-1 text-xs text-base-content/55">{t("processing.stat.costBasis")}</div>
        </div>
        <div className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
          <div className="text-xs uppercase text-base-content/50">{t("processing.stat.topModel")}</div>
          <div className="mt-1 truncate text-sm font-semibold">
            {aiUsage.data?.by_model[0] ? `${aiUsage.data.by_model[0].route_name} / ${aiUsage.data.by_model[0].model_name}` : "-"}
          </div>
          <div className="mt-1 text-xs text-base-content/55">
            {aiUsage.data?.by_model[0] ? t("processing.stat.tokensCount", { count: formatCompactNumber(aiUsage.data.by_model[0].total_tokens) }) : t("processing.stat.noCalls")}
          </div>
        </div>
      </section>

      {aiUsage.data?.by_layer.length ? (
        <section className="mb-4 rounded border border-base-300 bg-base-100 p-4 shadow-sm">
          <div className="mb-3 text-xs font-semibold uppercase text-base-content/55">{t("processing.byLayer.title")}</div>
          <div className="grid gap-2 md:grid-cols-2">
            {aiUsage.data.by_layer.map((layer) => (
              <div key={layer.ai_layer || "unknown"} className="rounded bg-base-200/40 p-3 text-xs">
                <div className="mb-1 font-semibold text-base-content">{layer.ai_layer}</div>
                <div className="grid gap-1 text-base-content/65">
                  <span>{t("processing.byLayer.calls", { count: layer.call_count, failed: layer.failure_count })}</span>
                  <span>{t("processing.byLayer.tokensCost", { tokens: formatCompactNumber(layer.total_tokens), cost: formatUsd(layer.estimated_cost_usd) })}</span>
                  <span>{t("processing.byLayer.avgLatency", { ms: layer.avg_latency_ms ?? "-" })}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="mb-4 grid gap-2 xl:grid-cols-[minmax(220px,1fr)_170px_220px_110px_170px_170px]">
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
        <select className="select select-bordered select-sm" value={translationStatus} onChange={(event) => setTranslationStatus(event.target.value)}>
          <option value="">{t("processing.filter.allL1")}</option>
          {TRANSLATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={classificationStatus} onChange={(event) => setClassificationStatus(event.target.value)}>
          <option value="">{t("processing.filter.allL2")}</option>
          {CLASSIFICATION_STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
      </div>

      <div className="mb-4 grid gap-2 md:grid-cols-[180px_180px_minmax(220px,1fr)]">
        <select className="select select-bordered select-sm" value={classificationStage} onChange={(event) => setClassificationStage(event.target.value)}>
          <option value="">{t("processing.filter.allL2Stages")}</option>
          {CLASSIFICATION_STAGES.map((stage) => (
            <option key={stage} value={stage}>
              {stage}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={isRelevant} onChange={(event) => setIsRelevant(event.target.value)}>
          <option value="">{t("processing.filter.allRelevance")}</option>
          <option value="true">{t("processing.filter.relevant")}</option>
          <option value="false">{t("processing.filter.notRelevant")}</option>
        </select>
        <input className="input input-bordered input-sm" placeholder="source_group" value={sourceGroup} onChange={(event) => setSourceGroup(event.target.value)} />
      </div>

      {query.error ? <ErrorPanel error={query.error} /> : null}

      <div className="mb-3 text-xs text-base-content/50">
        {t("processing.showing", { shown: query.data?.items.length ?? 0, total: query.data?.total ?? 0 })}
      </div>

      <div className="space-y-3">
        {query.isLoading
          ? Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="rounded border border-base-300 bg-base-100 p-4">
              <div className="skeleton mb-3 h-4 w-48" />
              <div className="skeleton mb-4 h-5 w-3/4" />
              <div className="grid gap-3 lg:grid-cols-2">
                <div className="skeleton h-28 w-full" />
                <div className="skeleton h-28 w-full" />
              </div>
            </div>
          ))
          : null}
        {query.data?.items.length === 0 ? (
          <div className="rounded border border-base-300 bg-base-100 py-10 text-center text-base-content/50">
            {t("processing.empty")}
          </div>
        ) : null}
        {query.data?.items.map((item) => {
          const title = item.title || rawItemSummary(item, i18n.language) || item.raw_item_id;
          const classificationModel = modelLabel(item.classification_model_provider, item.classification_model_name);
          const translationModel = modelLabel(item.translation_model_provider, item.translation_model);

          return (
            <article key={item.raw_item_id} className="rounded border border-base-300 bg-base-100 p-4 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-base-content/60">
                <span>{formatTime(item.pipeline_updated_at || item.ingested_at)}</span>
                <span className="font-medium text-base-content">{item.source_name}</span>
                <span className="rounded bg-base-200 px-2 py-0.5">{item.source_type}</span>
                <span className="rounded bg-base-200 px-2 py-0.5">{item.source_group}</span>
                <OfficialBadge value={item.official_level} />
                <PriorityBadge value={item.priority} />
              </div>

              <h2 className="mb-3 line-clamp-2 text-sm font-semibold leading-6 text-base-content">{title}</h2>

              <div className="grid gap-3 lg:grid-cols-2">
                <LayerBlock
                  title={t("processing.layer1Title")}
                  status={item.translation_status}
                  model={translationModel}
                  updatedAt={item.translation_updated_at}
                  error={item.translation_error}
                >
                  <div>
                    <span className="mr-2 font-medium text-base-content/75">{t("processing.field.inputChars")}</span>
                    <span>{item.translation_input_chars ?? "-"}</span>
                  </div>
                  <UsageRow
                    callCount={item.translation_call_count}
                    totalTokens={item.translation_total_tokens}
                    inputTokens={item.translation_input_tokens}
                    outputTokens={item.translation_output_tokens}
                    cost={item.translation_estimated_cost_usd}
                  />
                </LayerBlock>

                <LayerBlock
                  title={t("processing.layer2Title")}
                  status={item.classification_status || "pending"}
                  model={classificationModel}
                  updatedAt={item.classification_updated_at}
                  error={item.classification_error}
                >
                  <div>
                    <span className="mr-2 font-medium text-base-content/75">{t("processing.field.stage")}</span>
                    <span>{item.classification_stage || "-"}</span>
                  </div>
                  <div>
                    <span className="mr-2 font-medium text-base-content/75">{t("processing.field.relevance")}</span>
                    <span>{item.is_relevant === null || item.is_relevant === undefined ? "-" : item.is_relevant ? t("processing.relevance.yes") : t("processing.relevance.no")}</span>
                  </div>
                  <div>
                    <span className="mr-2 font-medium text-base-content/75">{t("processing.field.score")}</span>
                    <Score value={item.relevance_score} />
                  </div>
                  <UsageRow
                    callCount={item.classification_call_count}
                    totalTokens={item.classification_total_tokens}
                    inputTokens={item.classification_input_tokens}
                    outputTokens={item.classification_output_tokens}
                    cost={item.classification_estimated_cost_usd}
                  />
                  {item.filter_reason ? (
                    <div>
                      <span className="mr-2 font-medium text-base-content/75">{t("processing.field.reason")}</span>
                      <span>{item.filter_reason}</span>
                    </div>
                  ) : null}
                </LayerBlock>
              </div>

              <div className="mt-3 grid gap-2 text-xs text-base-content/55 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                <div className="min-w-0">
                  <span className="mr-2 font-medium text-base-content/70">raw_item_id</span>
                  <span className="break-all font-mono">{item.raw_item_id}</span>
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
