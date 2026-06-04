import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Source, SourcePayload } from "../api/types";
import { OfficialBadge, PriorityBadge, StatusBadge } from "../components/Badges";
import { ErrorPanel } from "../components/DataState";
import { formatTime, Score, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

const SOURCE_TYPES = ["telegram", "rss", "atom", "html_polling", "api"];
const PRIORITIES = ["P0", "P1", "P2", "P3"];
const OFFICIAL_LEVELS = ["official", "semi_official", "unofficial", "unofficial_mirror", "aggregator"];
const LANGUAGES = ["en", "fa", "he", "ar", "zh", "mixed", "unknown"];
const SOURCE_GROUPS = [
  "us_trump",
  "us_fed",
  "us_military",
  "us_diplomacy",
  "us_sanctions",
  "iran_government",
  "iran_external_media",
  "iran_irgc_adjacent",
  "iran_irgc_official",
  "iran_supreme_leader",
  "iran_conservative",
  "israel_military",
  "israel_diplomacy",
  "israel_media",
  "market_squawk",
  "osint_aggregator",
  "international_media"
];
const TRANSLATION_POLICIES = ["disabled", "summary_only", "full"];
const TRANSLATION_PRIORITIES = ["normal", "high"];
const SEVERITIES = ["S", "A", "B", "C"];

type SourceFormState = Omit<SourcePayload, "source_config"> & {
  source_config: Record<string, unknown>;
};

function defaultSourceForm(): SourceFormState {
  return {
    name: "",
    handle_or_url: "",
    source_type: "telegram",
    source_group: "market_squawk",
    official_level: "aggregator",
    stance: "",
    language: "en",
    priority: "P2",
    reliability_score: 50,
    latency_score: 50,
    requires_confirmation: true,
    translation_policy: "full",
    translation_priority: "normal",
    translation_max_chars: null,
    always_full_translate: false,
    telegram_alert_enabled: true,
    pushover_alert_enabled: false,
    telegram_min_severity: "B",
    pushover_min_severity: "S",
    alert_weight: 50,
    alert_rate_limit_per_hour: null,
    alert_cooldown_minutes: null,
    enabled: true,
    source_config: {}
  };
}

function formFromSource(source: Source): SourceFormState {
  return {
    ...defaultSourceForm(),
    name: source.name,
    handle_or_url: source.handle_or_url,
    source_type: source.source_type,
    source_group: source.source_group,
    official_level: source.official_level,
    stance: source.stance ?? "",
    language: source.language ?? "unknown",
    priority: source.priority,
    reliability_score: source.reliability_score,
    latency_score: source.latency_score,
    requires_confirmation: source.requires_confirmation,
    translation_policy: source.translation_policy,
    translation_priority: source.translation_priority,
    translation_max_chars: source.translation_max_chars ?? null,
    always_full_translate: source.always_full_translate,
    telegram_alert_enabled: source.telegram_alert_enabled,
    pushover_alert_enabled: source.pushover_alert_enabled,
    telegram_min_severity: source.telegram_min_severity,
    pushover_min_severity: source.pushover_min_severity,
    alert_weight: source.alert_weight,
    alert_rate_limit_per_hour: source.alert_rate_limit_per_hour ?? null,
    alert_cooldown_minutes: source.alert_cooldown_minutes ?? null,
    enabled: source.enabled,
    source_config: {}
  };
}

function payloadFromForm(form: SourceFormState): SourcePayload {
  return {
    ...form,
    stance: form.stance || null,
    language: form.language === "unknown" ? null : form.language,
    translation_max_chars: form.translation_max_chars === null ? null : Number(form.translation_max_chars),
    alert_rate_limit_per_hour: form.alert_rate_limit_per_hour === null ? null : Number(form.alert_rate_limit_per_hour),
    alert_cooldown_minutes: form.alert_cooldown_minutes === null ? null : Number(form.alert_cooldown_minutes)
  };
}

function FieldLabel({ children }: { children: string }) {
  return <label className="label py-1 text-xs font-medium text-base-content/70">{children}</label>;
}

function SelectField({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      <select className="select select-bordered select-sm w-full" value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

function NumberField({
  label,
  value,
  min = 0,
  max,
  onChange
}: {
  label: string;
  value: number | null;
  min?: number;
  max?: number;
  onChange: (value: number | null) => void;
}) {
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      <input
        className="input input-bordered input-sm w-full"
        min={min}
        max={max}
        type="number"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))}
      />
    </div>
  );
}

function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-3 rounded border border-base-300 px-3 py-2 text-sm">
      <span>{label}</span>
      <input className="toggle toggle-sm" type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function SourceModal({
  mode,
  form,
  error,
  isPending,
  onClose,
  onSubmit,
  setForm
}: {
  mode: "create" | "edit";
  form: SourceFormState;
  error: unknown;
  isPending: boolean;
  onClose: () => void;
  onSubmit: () => void;
  setForm: (form: SourceFormState) => void;
}) {
  const { t } = useTranslation();
  const title = mode === "create" ? t("sources.addSource") : t("sources.editSource");
  const set = <K extends keyof SourceFormState>(key: K, value: SourceFormState[K]) => setForm({ ...form, [key]: value });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-3">
      <div className="max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded border border-base-300 bg-base-100 shadow-xl">
        <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-base-300 bg-base-100 px-4 py-3">
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            <p className="text-xs text-base-content/55">{t("sources.modalSubtitle")}</p>
          </div>
          <button className="btn btn-ghost btn-sm" type="button" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>

        <div className="space-y-5 p-4">
          {error ? <ErrorPanel error={error} /> : null}

          <section>
            <h3 className="mb-2 text-sm font-semibold">{t("sources.section.identity")}</h3>
            <div className="grid gap-3 lg:grid-cols-2">
              <div>
                <FieldLabel>{t("sources.field.name")}</FieldLabel>
                <input className="input input-bordered input-sm w-full" value={form.name} onChange={(event) => set("name", event.target.value)} />
              </div>
              <div>
                <FieldLabel>{t("sources.field.handleOrUrl")}</FieldLabel>
                <input className="input input-bordered input-sm w-full" value={form.handle_or_url} onChange={(event) => set("handle_or_url", event.target.value)} />
              </div>
              <SelectField label={t("sources.field.sourceType")} value={form.source_type} options={SOURCE_TYPES} onChange={(value) => set("source_type", value)} />
              <SelectField label={t("sources.field.sourceGroup")} value={form.source_group} options={SOURCE_GROUPS} onChange={(value) => set("source_group", value)} />
              <SelectField label={t("sources.field.officialLevel")} value={form.official_level} options={OFFICIAL_LEVELS} onChange={(value) => set("official_level", value)} />
              <SelectField label={t("sources.field.language")} value={form.language ?? "unknown"} options={LANGUAGES} onChange={(value) => set("language", value)} />
              <SelectField label={t("sources.field.priority")} value={form.priority} options={PRIORITIES} onChange={(value) => set("priority", value)} />
              <div>
                <FieldLabel>{t("sources.field.stance")}</FieldLabel>
                <input className="input input-bordered input-sm w-full" value={form.stance ?? ""} onChange={(event) => set("stance", event.target.value)} />
              </div>
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">{t("sources.section.scoring")}</h3>
            <div className="grid gap-3 lg:grid-cols-4">
              <NumberField label={t("sources.field.reliabilityScore")} value={form.reliability_score} max={100} onChange={(value) => set("reliability_score", value ?? 0)} />
              <NumberField label={t("sources.field.latencyScore")} value={form.latency_score} max={100} onChange={(value) => set("latency_score", value ?? 0)} />
              <NumberField label={t("sources.field.alertWeight")} value={form.alert_weight} max={100} onChange={(value) => set("alert_weight", value ?? 0)} />
              <ToggleField label={t("sources.field.requiresConfirmation")} checked={form.requires_confirmation} onChange={(checked) => set("requires_confirmation", checked)} />
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">{t("sources.section.translation")}</h3>
            <div className="grid gap-3 lg:grid-cols-4">
              <SelectField label={t("sources.field.policy")} value={form.translation_policy} options={TRANSLATION_POLICIES} onChange={(value) => set("translation_policy", value)} />
              <SelectField label={t("sources.field.priority")} value={form.translation_priority} options={TRANSLATION_PRIORITIES} onChange={(value) => set("translation_priority", value)} />
              <NumberField label={t("sources.field.maxChars")} value={form.translation_max_chars ?? null} onChange={(value) => set("translation_max_chars", value)} />
              <ToggleField label={t("sources.field.alwaysFullTranslate")} checked={form.always_full_translate} onChange={(checked) => set("always_full_translate", checked)} />
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">{t("sources.section.alertPolicy")}</h3>
            <div className="grid gap-3 lg:grid-cols-4">
              <ToggleField label={t("sources.field.telegramAlerts")} checked={form.telegram_alert_enabled} onChange={(checked) => set("telegram_alert_enabled", checked)} />
              <SelectField label={t("sources.field.telegramMinSeverity")} value={form.telegram_min_severity} options={SEVERITIES} onChange={(value) => set("telegram_min_severity", value)} />
              <ToggleField label={t("sources.field.pushoverAlerts")} checked={form.pushover_alert_enabled} onChange={(checked) => set("pushover_alert_enabled", checked)} />
              <SelectField label={t("sources.field.pushoverMinSeverity")} value={form.pushover_min_severity} options={SEVERITIES} onChange={(value) => set("pushover_min_severity", value)} />
              <NumberField label={t("sources.field.rateLimit")} value={form.alert_rate_limit_per_hour ?? null} onChange={(value) => set("alert_rate_limit_per_hour", value)} />
              <NumberField label={t("sources.field.cooldownMinutes")} value={form.alert_cooldown_minutes ?? null} onChange={(value) => set("alert_cooldown_minutes", value)} />
              <ToggleField label={t("sources.field.enabled")} checked={form.enabled} onChange={(checked) => set("enabled", checked)} />
            </div>
          </section>
        </div>

        <div className="sticky bottom-0 flex justify-end gap-2 border-t border-base-300 bg-base-100 px-4 py-3">
          <button className="btn btn-ghost btn-sm" type="button" onClick={onClose}>
            {t("common.cancel")}
          </button>
          <button className="btn btn-primary btn-sm" type="button" disabled={isPending || !form.name || !form.handle_or_url} onClick={onSubmit}>
            {isPending ? t("common.saving") : t("common.save")}
          </button>
        </div>
      </div>
    </div>
  );
}

function SourceCard({
  source,
  healthStatus,
  lastSuccess,
  onEdit,
  onEnable,
  onDisable,
  onArchive,
  actionPending
}: {
  source: Source;
  healthStatus?: string;
  lastSuccess?: string | null;
  onEdit: () => void;
  onEnable: () => void;
  onDisable: () => void;
  onArchive: () => void;
  actionPending: boolean;
}) {
  const { t } = useTranslation();
  const status = source.archived_at ? "archived" : source.enabled ? healthStatus || "unknown" : "disabled";
  return (
    <article className="rounded border border-base-300 bg-base-100 p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold">{source.name}</h2>
            <StatusBadge value={status} />
            <PriorityBadge value={source.priority} />
            <OfficialBadge value={source.official_level} />
          </div>
          <Truncate className="text-sm text-base-content/60" text={source.handle_or_url} />
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-base-content/65">
            <span className="rounded bg-base-200 px-2 py-1">{source.source_type}</span>
            <span className="rounded bg-base-200 px-2 py-1">{source.source_group}</span>
            <span className="rounded bg-base-200 px-2 py-1">{source.language || t("sources.card.languageFallback")}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-outline btn-sm" type="button" onClick={onEdit}>
            {t("common.edit")}
          </button>
          {source.enabled ? (
            <button className="btn btn-outline btn-sm" type="button" disabled={actionPending} onClick={onDisable}>
              {t("common.disable")}
            </button>
          ) : (
            <button className="btn btn-outline btn-sm" type="button" disabled={actionPending} onClick={onEnable}>
              {t("common.enable")}
            </button>
          )}
          <button className="btn btn-outline btn-sm text-error" type="button" disabled={actionPending || Boolean(source.archived_at)} onClick={onArchive}>
            {t("common.archive")}
          </button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <div className="text-xs text-base-content/50">{t("sources.card.reliability")}</div>
          <Score value={source.reliability_score} />
        </div>
        <div>
          <div className="text-xs text-base-content/50">{t("sources.card.latency")}</div>
          <Score value={source.latency_score} />
        </div>
        <div>
          <div className="text-xs text-base-content/50">{t("sources.card.rawItems24h")}</div>
          <span className="font-mono text-sm">{source.raw_items_24h ?? 0}</span>
        </div>
        <div>
          <div className="text-xs text-base-content/50">{t("sources.card.events24h")}</div>
          <span className="font-mono text-sm">{source.events_24h ?? 0}</span>
        </div>
        <div>
          <div className="text-xs text-base-content/50">{t("sources.card.lastItem")}</div>
          <span className="text-sm">{formatTime(source.last_raw_item_at)}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-base-content/65">
        <span className="rounded bg-base-200 px-2 py-1">TG {source.telegram_alert_enabled ? source.telegram_min_severity : t("sources.card.off")}</span>
        <span className="rounded bg-base-200 px-2 py-1">Pushover {source.pushover_alert_enabled ? source.pushover_min_severity : t("sources.card.off")}</span>
        <span className="rounded bg-base-200 px-2 py-1">{t("sources.card.weight", { value: source.alert_weight })}</span>
        <span className="rounded bg-base-200 px-2 py-1">{t("sources.card.lastSuccess", { time: formatTime(lastSuccess) })}</span>
      </div>
    </article>
  );
}

export function Sources() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [sourceType, setSourceType] = useState("");
  const [sourceGroup, setSourceGroup] = useState("");
  const [priority, setPriority] = useState("");
  const [enabled, setEnabled] = useState("");
  const [archived, setArchived] = useState("false");
  const [modal, setModal] = useState<{ mode: "create" | "edit"; source?: Source; form: SourceFormState } | null>(null);

  const sourceParams = { page_size: 200, source_type: sourceType, source_group: sourceGroup, priority, enabled, archived };
  const sources = useQuery({
    queryKey: ["sources", sourceParams],
    queryFn: () => api.sources(sourceParams),
    refetchInterval: 60000
  });
  const health = useQuery({
    queryKey: ["source-health"],
    queryFn: () => api.sourceHealth({ page_size: 300 }),
    refetchInterval: 30000
  });
  const healthBySource = useMemo(() => new Map(health.data?.items.map((item) => [item.source_id, item])), [health.data?.items]);

  const invalidateSources = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sources"] }),
      queryClient.invalidateQueries({ queryKey: ["source-health"] }),
      queryClient.invalidateQueries({ queryKey: ["timeline-sources"] })
    ]);
  };

  const createMutation = useMutation({
    mutationFn: (payload: SourcePayload) => api.createSource(payload),
    onSuccess: async () => {
      setModal(null);
      await invalidateSources();
    }
  });
  const updateMutation = useMutation({
    mutationFn: ({ sourceId, payload }: { sourceId: string; payload: Partial<SourcePayload> }) => api.updateSource(sourceId, payload),
    onSuccess: async () => {
      setModal(null);
      await invalidateSources();
    }
  });
  const actionMutation = useMutation({
    mutationFn: ({ action, sourceId }: { action: "enable" | "disable" | "archive"; sourceId: string }) => {
      if (action === "enable") return api.enableSource(sourceId);
      if (action === "disable") return api.disableSource(sourceId);
      return api.archiveSource(sourceId);
    },
    onSuccess: invalidateSources
  });

  const modalError = createMutation.error ?? updateMutation.error;
  const modalPending = createMutation.isPending || updateMutation.isPending;

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title={t("sources.title")} description={t("sources.description")} />
        <button className="btn btn-primary btn-sm" type="button" onClick={() => setModal({ mode: "create", form: defaultSourceForm() })}>
          {t("sources.addSource")}
        </button>
      </div>

      <div className="mb-4 grid gap-3 rounded border border-base-300 bg-base-100 p-3 sm:grid-cols-2 lg:grid-cols-5">
        <select className="select select-bordered select-sm w-full" value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
          <option value="">{t("sources.filter.allSourceTypes")}</option>
          {SOURCE_TYPES.map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
        <select className="select select-bordered select-sm w-full" value={sourceGroup} onChange={(event) => setSourceGroup(event.target.value)}>
          <option value="">{t("sources.filter.allSourceGroups")}</option>
          {SOURCE_GROUPS.map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
        <select className="select select-bordered select-sm w-full" value={priority} onChange={(event) => setPriority(event.target.value)}>
          <option value="">{t("sources.filter.allPriorities")}</option>
          {PRIORITIES.map((value) => (
            <option key={value} value={value}>{value}</option>
          ))}
        </select>
        <select className="select select-bordered select-sm w-full" value={enabled} onChange={(event) => setEnabled(event.target.value)}>
          <option value="">{t("sources.filter.allEnabled")}</option>
          <option value="true">{t("sources.filter.enabled")}</option>
          <option value="false">{t("sources.filter.disabled")}</option>
        </select>
        <select className="select select-bordered select-sm w-full" value={archived} onChange={(event) => setArchived(event.target.value)}>
          <option value="">{t("sources.filter.allArchive")}</option>
          <option value="false">{t("sources.filter.activeRegistry")}</option>
          <option value="true">{t("sources.filter.archived")}</option>
        </select>
      </div>

      {sources.error ? <ErrorPanel error={sources.error} /> : null}
      {health.error ? <ErrorPanel error={health.error} /> : null}
      {actionMutation.error ? <ErrorPanel error={actionMutation.error} /> : null}

      <div className="mb-3 text-sm text-base-content/60">
        {sources.isLoading ? t("sources.loading") : t("sources.count", { count: sources.data?.total ?? 0 })}
      </div>

      <div className="space-y-3">
        {sources.data?.items.length === 0 ? (
          <div className="rounded border border-base-300 bg-base-100 py-10 text-center text-base-content/50">{t("sources.empty")}</div>
        ) : null}
        {sources.data?.items.map((source) => {
          const sourceHealth = healthBySource.get(source.id);
          return (
            <SourceCard
              key={source.id}
              source={source}
              healthStatus={sourceHealth?.status}
              lastSuccess={sourceHealth?.last_success_at}
              actionPending={actionMutation.isPending}
              onEdit={() => setModal({ mode: "edit", source, form: formFromSource(source) })}
              onEnable={() => actionMutation.mutate({ action: "enable", sourceId: source.id })}
              onDisable={() => actionMutation.mutate({ action: "disable", sourceId: source.id })}
              onArchive={() => {
                if (window.confirm(t("sources.archiveConfirm", { name: source.name }))) {
                  actionMutation.mutate({ action: "archive", sourceId: source.id });
                }
              }}
            />
          );
        })}
      </div>

      {modal ? (
        <SourceModal
          mode={modal.mode}
          form={modal.form}
          error={modalError}
          isPending={modalPending}
          setForm={(form) => setModal({ ...modal, form })}
          onClose={() => setModal(null)}
          onSubmit={() => {
            const payload = payloadFromForm(modal.form);
            if (modal.mode === "create") {
              createMutation.mutate(payload);
            } else if (modal.source) {
              updateMutation.mutate({ sourceId: modal.source.id, payload });
            }
          }}
        />
      ) : null}
    </>
  );
}
