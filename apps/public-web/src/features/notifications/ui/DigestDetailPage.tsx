import { AlertTriangle, ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { useLanguage, useLocalizedPath } from "../../../i18n";
import type { DeliveryLanguage } from "../domain/models";
import { useDigest } from "../domain/queries";

export function DigestDetailPage() {
  const { digestId } = useParams();
  const uiLanguage = useLanguage();
  const chinese = uiLanguage === "zh-Hant";
  const language: DeliveryLanguage = chinese ? "zh-Hant" : "en";
  const to = useLocalizedPath();
  const digest = useDigest(digestId, language);

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
      <Link className="btn btn-ghost btn-sm mb-6" to={to("/digests")}><ArrowLeft className="h-4 w-4" />{chinese ? "返回摘要" : "Back to digests"}</Link>
      {digest.isPending && <div className="skeleton h-72 w-full" />}
      {digest.isError && <div className="alert alert-error"><span>{chinese ? "無法讀取此摘要。請確認登入與 News 訂閱狀態。" : "This digest could not be loaded. Check your sign-in and News subscription."}</span></div>}
      {digest.data?.status === "invalidated" && <div className="alert alert-warning"><AlertTriangle className="h-5 w-5" /><div><h1 className="font-semibold">{chinese ? "此摘要已撤回" : "This digest was withdrawn"}</h1><p>{digest.data.invalidation_reason ?? (chinese ? "來源內容已撤回或有重大更正。" : "Source content was withdrawn or materially corrected.")}</p></div></div>}
      {digest.data?.status === "language_unavailable" && <div className="alert alert-warning"><span>{chinese ? "此語言版本尚未完成。" : "This language edition is unavailable."}</span></div>}
      {digest.data?.status === "ready" && <article className="rounded-box border border-base-300 bg-base-200 p-6 sm:p-8"><p className="font-mono text-xs uppercase tracking-[0.18em] text-primary">{digest.data.topic.replace("_", " ")} · {new Date(digest.data.window_start).toLocaleDateString()}</p><h1 className="mt-4 text-3xl font-bold">{digest.data.title}</h1><p className="mt-5 text-lg leading-8 text-base-content/75">{digest.data.overview}</p>{digest.data.coverage_truncated && <p className="mt-4 text-sm text-warning">{chinese ? "輸入達到上限，內容不代表完整涵蓋。" : "The input limit was reached; coverage is not exhaustive."}</p>}<div className="mt-8 space-y-6">{digest.data.developments?.map((item, index) => <section key={`${index}-${item.text}`}><h2 className="font-mono text-xs text-base-content/45">{String(index + 1).padStart(2, "0")}</h2><p className="mt-2 leading-7">{item.text}</p><div className="mt-3 flex flex-wrap gap-2">{item.event_ids.map((eventId) => <Link key={eventId} className="link link-primary text-sm" to={to(`/events/${eventId}`)}>{chinese ? "來源事件" : "Source event"}</Link>)}</div></section>)}</div></article>}
    </div>
  );
}
