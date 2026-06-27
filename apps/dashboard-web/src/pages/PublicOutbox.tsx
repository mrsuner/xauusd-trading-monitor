import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import type { PublicOutboxItem } from "../api/types";
import { api } from "../api/client";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Score, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

type ChannelKey = "web" | "telegram" | "x";

const CHANNELS: ChannelKey[] = ["web", "telegram", "x"];
const STATUSES = ["", "pending", "sending", "sent", "retry", "failed", "skipped"] as const;
const APPROVAL_FILTERS = ["", "true", "false"] as const;
const ZH_HANT = "zh-Hant";
const ENGLISH = "en";

function preferredLanguages(language?: string | null): string[] {
  const preferred = language?.startsWith("zh") ? ZH_HANT : ENGLISH;
  return [...new Set([preferred, ENGLISH, ZH_HANT])];
}

function translationFor(item: PublicOutboxItem, language?: string | null) {
  const translations = item.translations ?? [];
  for (const preferred of preferredLanguages(language)) {
    const translation = translations.find((candidate) => candidate.language === preferred);
    if (translation?.title || translation?.summary) {
      return translation;
    }
  }
  return translations.find((candidate) => candidate.title || candidate.summary);
}

function titleFor(item: PublicOutboxItem, language?: string | null) {
  const translation = translationFor(item, language);
  return translation?.title || item.event_title || translation?.summary;
}

function summaryFor(item: PublicOutboxItem, language?: string | null) {
  const translation = translationFor(item, language);
  return translation?.summary || item.event_summary_zh;
}

function channelState(item: PublicOutboxItem, channel: ChannelKey) {
  if (channel === "web") {
    return {
      status: item.publish_status_web,
      publishedAt: item.published_web_at,
      retryCount: item.retry_count_web,
      error: item.last_error_web,
      externalId: item.external_web_id,
      nextRetryAt: item.next_retry_web_at
    };
  }
  if (channel === "telegram") {
    return {
      status: item.publish_status_telegram,
      publishedAt: item.published_telegram_at,
      retryCount: item.retry_count_telegram,
      error: item.last_error_telegram,
      externalId: item.external_telegram_message_id,
      nextRetryAt: item.next_retry_telegram_at
    };
  }
  return {
    status: item.publish_status_x,
    publishedAt: item.published_x_at,
    retryCount: item.retry_count_x,
    error: item.last_error_x,
    externalId: item.external_x_post_id,
    nextRetryAt: item.next_retry_x_at
  };
}

function ChannelCell({ item, channel }: { item: PublicOutboxItem; channel: ChannelKey }) {
  const { t } = useTranslation();
  const state = channelState(item, channel);
  return (
    <div className="min-w-0 space-y-1">
      <StatusBadge value={state.status} />
      <div className="text-xs text-base-content/60">
        {state.publishedAt ? t("publicOutbox.publishedAt", { time: formatTime(state.publishedAt) }) : t("publicOutbox.notPublished")}
      </div>
      {state.retryCount > 0 ? <div className="text-xs text-warning">{t("publicOutbox.retryCount", { count: state.retryCount })}</div> : null}
      {state.nextRetryAt ? <div className="text-xs text-base-content/55">{t("publicOutbox.nextRetry", { time: formatTime(state.nextRetryAt) })}</div> : null}
      {state.externalId ? <Truncate className="text-xs text-base-content/55" text={t("publicOutbox.externalId", { id: state.externalId })} /> : null}
      {state.error ? <Truncate className="text-xs text-error" text={state.error} /> : null}
    </div>
  );
}

export function PublicOutbox() {
  const { t, i18n } = useTranslation();
  const [channel, setChannel] = useState("");
  const [publishStatus, setPublishStatus] = useState("");
  const [approvedForPublic, setApprovedForPublic] = useState("");
  const [severity, setSeverity] = useState("");
  const [q, setQ] = useState("");

  const query = useQuery({
    queryKey: ["public-outbox", channel, publishStatus, approvedForPublic, severity, q],
    queryFn: () =>
      api.publicOutbox({
        page_size: 75,
        channel,
        publish_status: publishStatus,
        approved_for_public: approvedForPublic,
        severity,
        q
      }),
    refetchInterval: 30000
  });

  return (
    <>
      <PageHeader title={t("publicOutbox.title")} description={t("publicOutbox.description")} />
      <div className="mb-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-[minmax(12rem,1fr)_10rem_10rem_10rem_10rem]">
        <input
          className="input input-bordered input-sm"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("common.keywordSearch")}
        />
        <select className="select select-bordered select-sm" value={channel} onChange={(event) => setChannel(event.target.value)}>
          <option value="">{t("publicOutbox.filter.allChannels")}</option>
          {CHANNELS.map((item) => (
            <option key={item} value={item}>
              {t(`publicOutbox.channel.${item}`)}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={publishStatus} onChange={(event) => setPublishStatus(event.target.value)}>
          {STATUSES.map((status) => (
            <option key={status || "all"} value={status}>
              {status || t("publicOutbox.filter.allStatuses")}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={approvedForPublic} onChange={(event) => setApprovedForPublic(event.target.value)}>
          {APPROVAL_FILTERS.map((value) => (
            <option key={value || "all"} value={value}>
              {value === "true" ? t("publicOutbox.filter.approved") : value === "false" ? t("publicOutbox.filter.notApproved") : t("publicOutbox.filter.allApproval")}
            </option>
          ))}
        </select>
        <select className="select select-bordered select-sm" value={severity} onChange={(event) => setSeverity(event.target.value)}>
          {["", "S", "A", "B", "C"].map((item) => (
            <option key={item || "all"} value={item}>
              {item || t("events.all")}
            </option>
          ))}
        </select>
      </div>
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm min-w-[1180px]">
          <thead>
            <tr>
              <th className="w-32">{t("publicOutbox.col.generated")}</th>
              <th className="w-16">{t("publicOutbox.col.severity")}</th>
              <th>{t("publicOutbox.col.content")}</th>
              <th className="w-24">{t("publicOutbox.col.score")}</th>
              <th className="w-24">{t("publicOutbox.col.approved")}</th>
              <th className="w-44">{t("publicOutbox.channel.web")}</th>
              <th className="w-44">{t("publicOutbox.channel.telegram")}</th>
              <th className="w-44">{t("publicOutbox.channel.x")}</th>
              <th className="w-32">{t("publicOutbox.col.updated")}</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <LoadingRows columns={9} /> : null}
            {query.data?.items.length === 0 ? <EmptyRow columns={9}>{t("publicOutbox.empty")}</EmptyRow> : null}
            {query.data?.items.map((item) => (
              <tr key={item.id}>
                <td>{formatTime(item.generated_at)}</td>
                <td><SeverityBadge value={item.severity} /></td>
                <td>
                  <Link className="link link-primary font-medium" to={`/events/${item.event_id}`}>
                    <Truncate text={titleFor(item, i18n.language)} />
                  </Link>
                  <Truncate className="text-xs text-base-content/55" text={summaryFor(item, i18n.language)} />
                  <div className="mt-1 flex min-w-0 flex-wrap gap-1">
                    {item.topic_tags.slice(0, 4).map((tag) => (
                      <span key={tag} className="badge badge-outline badge-xs">{tag}</span>
                    ))}
                  </div>
                </td>
                <td><Score value={item.relevance_score} /></td>
                <td>
                  <span className={`badge badge-sm ${item.approved_for_public ? "badge-success" : "badge-ghost"}`}>
                    {item.approved_for_public ? t("publicOutbox.approved") : t("publicOutbox.notApproved")}
                  </span>
                </td>
                <td><ChannelCell item={item} channel="web" /></td>
                <td><ChannelCell item={item} channel="telegram" /></td>
                <td><ChannelCell item={item} channel="x" /></td>
                <td>{formatTime(item.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
