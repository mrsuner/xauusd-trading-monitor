import { Bell, ExternalLink, RefreshCw, Send, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AccountApiError } from "../domain/api";
import { useAccountSession } from "../../account/domain/queries";
import { disableCurrentBrowser, enableCurrentBrowser, getWebPushStatus, isCurrentBrowserRegistered } from "../domain/webPush";
import type { WebPushStatus } from "../domain/webPush";
import type { NotificationPreferences } from "../domain/models";
import {
  useCreateTelegramLink,
  useNotificationChannels,
  useNotificationSettings,
  useSavePreferences,
  useSetTelegramEnabled,
  useSetPushEnabled,
  useSubscriptionCatalog,
  useUnlinkTelegram
} from "../domain/queries";
import { useI18n, useLanguage, useLocalizedPath } from "../../../i18n";

export function NotificationSettingsPage() {
  const t = useI18n().notifications;
  const language = useLanguage();
  const location = useLocation();
  const to = useLocalizedPath();
  const settings = useNotificationSettings();
  const channels = useNotificationChannels(settings.isSuccess);
  const catalog = useSubscriptionCatalog();
  const save = useSavePreferences();
  const createLink = useCreateTelegramLink();
  const setChannelEnabled = useSetTelegramEnabled();
  const setPushEnabled = useSetPushEnabled();
  const unlink = useUnlinkTelegram();
  const session = useAccountSession();
  const [draft, setDraft] = useState<NotificationPreferences | null>(null);
  const [webPushStatus, setWebPushStatus] = useState<WebPushStatus | null>(null);
  const [browserRegistered, setBrowserRegistered] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushError, setPushError] = useState(false);

  useEffect(() => {
    if (settings.data?.preferences) setDraft(settings.data.preferences);
  }, [settings.data?.preferences]);

  useEffect(() => {
    const userId = session.data?.user.id;
    if (!userId) return;
    let active = true;
    setBrowserRegistered(isCurrentBrowserRegistered(userId));
    getWebPushStatus(userId)
      .then((status) => { if (active) setWebPushStatus(status); });
    return () => { active = false; };
  }, [session.data?.user.id]);

  const channel = channels.data?.find((item) => item.type === "telegram");
  const pushChannel = channels.data?.find((item) => item.type === "push");
  const isActive = settings.data?.access === "active";
  const canSave = Boolean(
    draft && settings.data && (isActive || (settings.data.preferences.masterEnabled && !draft.masterEnabled))
  );
  const error = firstError(save.error, createLink.error, setChannelEnabled.error, setPushEnabled.error, unlink.error);

  if (settings.isPending) return <PageShell><div className="skeleton h-48 w-full" /></PageShell>;
  if (settings.error instanceof AccountApiError && settings.error.status === 401) {
    return (
      <PageShell>
        <section className="rounded-box border border-base-300 bg-base-200 p-6 sm:p-8">
          <h2 className="text-xl font-semibold">{t.signInTitle}</h2>
          <p className="mt-2 max-w-2xl text-base-content/65">{t.signInBody}</p>
          <Link
            className="btn btn-primary mt-5"
            to={to("/sign-in", `?returnTo=${encodeURIComponent(`${location.pathname}${location.search}`)}`)}
          >
            {t.signIn}
          </Link>
        </section>
      </PageShell>
    );
  }
  if (settings.isError || !draft) {
    return <PageShell><ErrorAlert message={t.loadError} /></PageShell>;
  }

  const categories = catalog.data?.categories ?? [];
  const tags = catalog.data?.tags ?? [];
  const categoryKeys = new Set(categories.map((item) => item.key));
  const tagKeys = new Set(tags.map((item) => item.key));
  const unavailable = [
    ...draft.categories.filter((key) => !categoryKeys.has(key)),
    ...draft.tags.filter((key) => !tagKeys.has(key))
  ];

  return (
    <PageShell>
      {!isActive && (
        <div className="alert alert-warning mb-6">
          <span>{t.upgradeRequired}</span>
        </div>
      )}
      {Boolean(error) && <ErrorAlert message={messageFor(error, t.requestError)} />}
      {pushError && <ErrorAlert message={t.pushError} />}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <form
          className="rounded-box border border-base-300 bg-base-200 p-5 sm:p-7"
          onSubmit={(event) => {
            event.preventDefault();
            save.mutate(draft);
          }}
        >
          <div className="flex items-start gap-3">
            <Bell className="mt-1 h-5 w-5 text-primary" />
            <div>
              <h2 className="text-xl font-semibold">{t.preferencesTitle}</h2>
              <p className="mt-1 text-sm text-base-content/60">{t.preferencesBody}</p>
            </div>
          </div>

          <label className="mt-6 flex cursor-pointer items-center justify-between gap-4 rounded-box border border-base-300 bg-base-100 p-4">
            <span>
              <span className="block font-medium">{t.masterLabel}</span>
              <span className="mt-1 block text-sm text-base-content/55">{t.masterBody}</span>
            </span>
            <input
              className="toggle toggle-primary"
              type="checkbox"
              checked={draft.masterEnabled}
              disabled={!isActive && !draft.masterEnabled}
              onChange={(event) => setDraft({ ...draft, masterEnabled: event.target.checked })}
            />
          </label>

          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <label className="form-control">
              <span className="label-text mb-2 font-medium">{t.severity}</span>
              <select
                className="select select-bordered w-full"
                value={draft.minSeverity}
                disabled={!isActive}
                onChange={(event) => setDraft({ ...draft, minSeverity: event.target.value as NotificationPreferences["minSeverity"] })}
              >
                <option value="S">S</option><option value="A">A</option><option value="B">B</option><option value="C">C</option>
              </select>
            </label>
            <label className="form-control">
              <span className="label-text mb-2 font-medium">{t.language}</span>
              <select
                className="select select-bordered w-full"
                value={draft.contentLanguage}
                disabled={!isActive}
                onChange={(event) => setDraft({ ...draft, contentLanguage: event.target.value as NotificationPreferences["contentLanguage"] })}
              >
                <option value="zh-Hant">繁體中文</option><option value="en">English</option>
              </select>
            </label>
          </div>

          <fieldset className="mt-7" disabled={!isActive || catalog.isPending || catalog.isError}>
            <legend className="font-semibold">{t.categories}</legend>
            <label className="mt-3 flex cursor-pointer items-center gap-3">
              <input
                className="checkbox checkbox-primary checkbox-sm"
                type="checkbox"
                checked={draft.matchAllCategories}
                onChange={(event) => setDraft({ ...draft, matchAllCategories: event.target.checked })}
              />
              <span>{t.allCategories}</span>
            </label>
            {!draft.matchAllCategories && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {categories.map((category) => (
                  <CheckOption
                    key={category.key}
                    label={language === "zh-Hant" ? category.label_zh : category.label_en}
                    checked={draft.categories.includes(category.key)}
                    onChange={() => setDraft({ ...draft, categories: toggleKey(draft.categories, category.key) })}
                  />
                ))}
              </div>
            )}
          </fieldset>

          <fieldset className="mt-7" disabled={!isActive || catalog.isPending || catalog.isError}>
            <legend className="font-semibold">{t.tags}</legend>
            <p className="mt-1 text-sm text-base-content/55">{t.tagsBody}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {tags.map((tag) => {
                const checked = draft.tags.includes(tag.key);
                return (
                  <label key={tag.key} className={`btn btn-sm ${checked ? "btn-primary" : "btn-outline"}`}>
                    <input
                      className="sr-only"
                      type="checkbox"
                      checked={checked}
                      onChange={() => setDraft({ ...draft, tags: toggleKey(draft.tags, tag.key) })}
                    />
                    {language === "zh-Hant" ? tag.label_zh : tag.label_en}
                  </label>
                );
              })}
            </div>
          </fieldset>

          {catalog.isError && <p className="mt-5 text-sm text-error">{t.catalogError}</p>}
          {unavailable.length > 0 && (
            <p className="mt-5 text-sm text-warning">{t.unavailableSelections}: {unavailable.join(", ")}</p>
          )}
          {save.isSuccess && <p className="mt-5 text-sm text-success">{t.saved}</p>}
          <button className="btn btn-primary mt-7" type="submit" disabled={!canSave || save.isPending || catalog.isError}>
            {save.isPending ? t.saving : t.save}
          </button>
        </form>

        <div className="space-y-6">
        <section className="rounded-box border border-base-300 bg-base-200 p-5 sm:p-6">
          <div className="flex items-center gap-3"><Send className="h-5 w-5 text-primary" /><h2 className="text-xl font-semibold">Telegram</h2></div>
          <p className="mt-2 text-sm text-base-content/60">{t.telegramBody}</p>
          {channels.isPending && <div className="skeleton mt-5 h-24 w-full" />}
          {channels.isError && <ErrorAlert message={t.channelLoadError} />}
          {!channel && channels.isSuccess && (
            <button className="btn btn-primary mt-5 w-full" disabled={!isActive || createLink.isPending} onClick={() => createLink.mutate()}>
              {createLink.isPending ? t.creatingLink : t.linkTelegram}
            </button>
          )}
          {createLink.data && !channel?.verified && (
            <div className="mt-5 rounded-box border border-primary/30 bg-primary/5 p-4">
              <p className="text-sm">{t.openTelegramBody}</p>
              <a className="btn btn-primary btn-sm mt-3" href={createLink.data.deepLink} target="_blank" rel="noreferrer">
                {t.openTelegram}<ExternalLink className="h-4 w-4" />
              </a>
              <button className="btn btn-ghost btn-sm mt-3" onClick={() => channels.refetch()}>
                <RefreshCw className="h-4 w-4" />{t.checkLink}
              </button>
            </div>
          )}
          {channel?.verified && (
            <div className="mt-5">
              <div className="flex items-center justify-between rounded-box border border-base-300 bg-base-100 p-4">
                <div><p className="font-medium">{t.linked}</p><p className="text-sm text-base-content/55">{channel.targetHint}</p></div>
                <input
                  className="toggle toggle-primary"
                  type="checkbox"
                  aria-label={t.channelEnabled}
                  checked={channel.enabled}
                  disabled={setChannelEnabled.isPending || (!isActive && !channel.enabled)}
                  onChange={(event) => setChannelEnabled.mutate(event.target.checked)}
                />
              </div>
              {channel.lastErrorCode && <p className="mt-3 text-sm text-warning">{t.channelNeedsAttention}</p>}
              <button
                className="btn btn-ghost btn-sm mt-4 text-error"
                disabled={unlink.isPending}
                onClick={() => { if (window.confirm(t.unlinkConfirm)) unlink.mutate(); }}
              >
                <Trash2 className="h-4 w-4" />{t.unlink}
              </button>
            </div>
          )}
          {channel && !channel.verified && !createLink.data && (
            <button className="btn btn-primary mt-5 w-full" disabled={!isActive || createLink.isPending} onClick={() => createLink.mutate()}>
              {t.linkTelegram}
            </button>
          )}
        </section>

        <section className="rounded-box border border-base-300 bg-base-200 p-5 sm:p-6">
          <div className="flex items-center gap-3"><Bell className="h-5 w-5 text-primary" /><h2 className="text-xl font-semibold">{t.pushTitle}</h2></div>
          <p className="mt-2 text-sm text-base-content/60">{t.pushBody}</p>
          {webPushStatus === "unsupported" && <p className="mt-4 text-sm text-warning">{t.pushUnsupported}</p>}
          {webPushStatus === "unconfigured" && <p className="mt-4 text-sm text-warning">{t.pushUnconfigured}</p>}
          {webPushStatus === "blocked" && <p className="mt-4 text-sm text-warning">{t.pushBlocked}</p>}
          {webPushStatus === "enabled" && <p className="mt-4 text-sm text-success">{t.pushThisBrowserEnabled}</p>}
          {webPushStatus === "available" && <p className="mt-4 text-sm text-base-content/60">{t.pushThisBrowserOff}</p>}
          {!settings.data.preferences.masterEnabled && <p className="mt-4 text-sm text-warning">{t.pushMasterRequired}</p>}
          {webPushStatus === "enabled" && !pushChannel?.enabled && <p className="mt-4 text-sm text-warning">{t.pushAccountPaused}</p>}
          {browserRegistered ? (
            <button className="btn btn-outline btn-sm mt-4" type="button" disabled={pushBusy} onClick={async () => {
              setPushBusy(true); setPushError(false);
              try {
                await disableCurrentBrowser();
                setWebPushStatus(await getWebPushStatus(session.data!.user.id));
                setBrowserRegistered(false);
              } catch { setPushError(true); } finally { setPushBusy(false); }
            }}>{t.pushDisableBrowser}</button>
          ) : (
            <button className="btn btn-primary btn-sm mt-4" type="button"
              disabled={!isActive || pushBusy || !session.data || webPushStatus !== "available"}
              onClick={async () => {
                setPushBusy(true); setPushError(false);
                try {
                  await enableCurrentBrowser(session.data!.user.id);
                  if (!pushChannel?.enabled) await setPushEnabled.mutateAsync(true);
                  setWebPushStatus(await getWebPushStatus(session.data!.user.id));
                  setBrowserRegistered(true);
                } catch {
                  setPushError(true);
                  setWebPushStatus(await getWebPushStatus(session.data!.user.id));
                  setBrowserRegistered(isCurrentBrowserRegistered(session.data!.user.id));
                } finally { setPushBusy(false); }
              }}>{t.pushEnableBrowser}</button>
          )}
          {pushChannel?.enabled && <button className="btn btn-ghost btn-sm mt-4 ml-2" type="button" disabled={setPushEnabled.isPending}
            onClick={() => setPushEnabled.mutate(false)}>{t.pushDisableAccount}</button>}
          {!pushChannel?.enabled && webPushStatus === "enabled" && <button className="btn btn-outline btn-sm mt-4 ml-2" type="button" disabled={!isActive || setPushEnabled.isPending}
            onClick={() => setPushEnabled.mutate(true)}>{t.pushEnableAccount}</button>}
          <p className="mt-4 text-xs text-base-content/50">{t.pushScope}</p>
        </section>
        </div>
      </div>
    </PageShell>
  );
}

function PageShell({ children }: { children: React.ReactNode }) {
  const t = useI18n().notifications;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">{t.eyebrow}</p>
      <h1 className="mt-3 text-3xl font-bold sm:text-4xl">{t.title}</h1>
      <p className="mb-8 mt-3 max-w-3xl text-base-content/65">{t.body}</p>
      {children}
    </div>
  );
}

function CheckOption({ label, checked, onChange }: { label: string; checked: boolean; onChange: () => void }) {
  return <label className="flex cursor-pointer items-center gap-3 rounded-field border border-base-300 bg-base-100 p-3"><input className="checkbox checkbox-primary checkbox-sm" type="checkbox" checked={checked} onChange={onChange} /><span>{label}</span></label>;
}

function ErrorAlert({ message }: { message: string }) {
  return <div className="alert alert-error mb-5"><span>{message}</span></div>;
}

function toggleKey(values: string[], key: string): string[] {
  return values.includes(key) ? values.filter((value) => value !== key) : [...values, key].sort();
}

function firstError(...errors: unknown[]): unknown {
  return errors.find(Boolean);
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof AccountApiError ? error.message : fallback;
}
