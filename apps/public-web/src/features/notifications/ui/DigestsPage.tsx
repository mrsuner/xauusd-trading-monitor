import { BookOpen, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useLanguage, useLocalizedPath } from "../../../i18n";
import { AccountApiError } from "../domain/api";
import type { DeliveryLanguage, DigestTopic } from "../domain/models";
import { useDigestPreferences, useDigests, useSaveDigestPreferences } from "../domain/queries";

const topics: Record<DigestTopic, { en: string; zh: string }> = {
  geopolitics: { en: "Geopolitics", zh: "地緣政治" },
  monetary: { en: "Monetary policy", zh: "貨幣政策" },
  energy: { en: "Energy", zh: "能源" },
  macro_data: { en: "Macro data", zh: "宏觀數據" }
};

export function DigestsPage() {
  const uiLanguage = useLanguage();
  const chinese = uiLanguage === "zh-Hant";
  const language: DeliveryLanguage = chinese ? "zh-Hant" : "en";
  const to = useLocalizedPath();
  const location = useLocation();
  const preferences = useDigestPreferences();
  const active = preferences.data?.access === "active";
  const digests = useDigests(language, active);
  const save = useSaveDigestPreferences();
  const [enabled, setEnabled] = useState(false);
  const [selected, setSelected] = useState<DigestTopic[]>([]);

  useEffect(() => {
    if (preferences.data) {
      setEnabled(preferences.data.preferences.enabled);
      setSelected(preferences.data.preferences.topics);
    }
  }, [preferences.data]);

  if (preferences.isPending) return <Shell chinese={chinese}><div className="skeleton h-48 w-full" /></Shell>;
  if (preferences.error instanceof AccountApiError && preferences.error.status === 401) {
    return <Shell chinese={chinese}><Notice title={chinese ? "登入後閱讀摘要" : "Sign in to read digests"} body={chinese ? "請先登入 TickBase 帳戶，再回到此頁。" : "Sign in to your TickBase account, then return to this page."}><Link className="btn btn-primary mt-4" to={to("/sign-in", `?returnTo=${encodeURIComponent(`${location.pathname}${location.search}`)}`)}>{chinese ? "登入 TickBase" : "Sign in to TickBase"}</Link></Notice></Shell>;
  }
  if (preferences.isError || !preferences.data) return <Shell chinese={chinese}><ErrorMessage chinese={chinese} /></Shell>;
  const canSave = active || (
    preferences.data.preferences.enabled
    && !enabled
    && sameTopics(selected, preferences.data.preferences.topics)
  );

  return (
    <Shell chinese={chinese}>
      {!active && <div className="alert alert-warning mb-6"><span>{chinese ? "有效的 News 訂閱才能啟用摘要及閱讀全文。" : "An active News subscription is required to enable digests and read full editions."}</span></div>}
      <section className="rounded-box border border-base-300 bg-base-200 p-5 sm:p-7">
        <h2 className="text-xl font-semibold">{chinese ? "摘要偏好" : "Digest preferences"}</h2>
        <p className="mt-2 text-sm text-base-content/60">{chinese ? "摘要選項與即時通知分開管理。每天每位使用者最多收到一則摘要通知。" : "Digest topics are independent from live alert filters. Each reader receives at most one digest notification per day."}</p>
        <label className="mt-5 flex items-center justify-between rounded-box border border-base-300 bg-base-100 p-4">
          <span className="font-medium">{chinese ? "每日 Telegram 摘要" : "Daily Telegram digest"}</span>
          <input className="toggle toggle-primary" type="checkbox" checked={enabled} disabled={!active && !enabled} onChange={(event) => setEnabled(event.target.checked)} />
        </label>
        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          {preferences.data.availableTopics.map((topic) => (
            <label key={topic} className="flex cursor-pointer items-center gap-3 rounded-field border border-base-300 bg-base-100 p-3">
              <input className="checkbox checkbox-primary checkbox-sm" type="checkbox" checked={selected.includes(topic)} disabled={!active} onChange={() => setSelected(toggle(selected, topic))} />
              <span>{chinese ? topics[topic].zh : topics[topic].en}</span>
            </label>
          ))}
        </div>
        {enabled && selected.length === 0 && <p className="mt-3 text-sm text-warning">{chinese ? "啟用前至少選擇一個主題。" : "Select at least one topic before enabling."}</p>}
        {save.isError && <p className="mt-3 text-sm text-error">{save.error instanceof Error ? save.error.message : (chinese ? "儲存失敗。" : "Save failed.")}</p>}
        {save.isSuccess && <p className="mt-3 text-sm text-success">{chinese ? "摘要偏好已儲存。" : "Digest preferences saved."}</p>}
        <button className="btn btn-primary mt-5" disabled={!canSave || save.isPending || (enabled && selected.length === 0)} onClick={() => save.mutate({ enabled, topics: selected })}><Save className="h-4 w-4" />{chinese ? "儲存偏好" : "Save preferences"}</button>
      </section>

      <section className="mt-8">
        <h2 className="text-xl font-semibold">{chinese ? "最近 90 天" : "Last 90 days"}</h2>
        {digests.isPending && active && <div className="skeleton mt-4 h-40 w-full" />}
        {digests.isError && <ErrorMessage chinese={chinese} />}
        {digests.data?.length === 0 && <p className="mt-4 text-base-content/60">{chinese ? "目前沒有可閱讀的摘要。" : "No digest editions are available yet."}</p>}
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {digests.data?.map((digest) => (
            <article key={digest.id} className="rounded-box border border-base-300 bg-base-200 p-5">
              <div className="flex items-center justify-between gap-3"><span className="badge badge-outline">{chinese ? topics[digest.topic].zh : topics[digest.topic].en}</span><time className="text-xs text-base-content/50">{new Date(digest.window_start).toLocaleDateString()}</time></div>
              <h3 className="mt-4 text-lg font-semibold">{digest.title ?? (digest.status === "invalidated" ? (chinese ? "此摘要已撤回" : "Digest withdrawn") : (chinese ? "此語言版本無法使用" : "Language unavailable"))}</h3>
              {digest.coverage_truncated && <p className="mt-2 text-xs text-warning">{chinese ? "輸入達到上限，內容不代表完整涵蓋。" : "The input limit was reached; coverage is not exhaustive."}</p>}
              <Link className="btn btn-ghost btn-sm mt-4" to={to(`/digests/${digest.id}`)}>{chinese ? "閱讀摘要" : "Read digest"}</Link>
            </article>
          ))}
        </div>
      </section>
    </Shell>
  );
}

function Shell({ chinese, children }: { chinese: boolean; children: React.ReactNode }) {
  return <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8"><p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">{chinese ? "共用主題摘要" : "Shared topic digests"}</p><h1 className="mt-3 text-3xl font-bold sm:text-4xl">{chinese ? "每日新聞摘要" : "Daily news digests"}</h1><p className="mb-8 mt-3 max-w-3xl text-base-content/65">{chinese ? "每個主題每日生成一次，所有讀者共用同一份經驗證內容與翻譯。" : "Each topic is generated once per day and shares the same validated content and translations across readers."}</p>{children}</div>;
}

function Notice({ title, body, children }: { title: string; body: string; children?: React.ReactNode }) {
  return <section className="rounded-box border border-base-300 bg-base-200 p-6"><h2 className="text-xl font-semibold">{title}</h2><p className="mt-2 text-base-content/65">{body}</p>{children}</section>;
}

function ErrorMessage({ chinese }: { chinese: boolean }) {
  return <div className="alert alert-error mt-4"><span>{chinese ? "摘要暫時無法使用。" : "Digests are temporarily unavailable."}</span></div>;
}

function toggle(values: DigestTopic[], topic: DigestTopic): DigestTopic[] {
  return values.includes(topic) ? values.filter((value) => value !== topic) : [...values, topic].sort();
}

function sameTopics(left: DigestTopic[], right: DigestTopic[]): boolean {
  return [...left].sort().join("|") === [...right].sort().join("|");
}
