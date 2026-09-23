import { Save, Settings2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { AccountApiError } from "../../account/domain/api";
import { useI18n, useLocalizedPath } from "../../../i18n";
import { useReaderPreferences, useSaveReaderPreferences } from "../domain/queries";
import type { ColorSchemePreference, ContentLanguage, ReaderPreferences } from "../domain/models";
import type { Severity } from "../../../api/types";

export function ReaderPreferencesPage() {
  const t = useI18n().reader;
  const to = useLocalizedPath();
  const location = useLocation();
  const preferences = useReaderPreferences();
  const save = useSaveReaderPreferences();
  const [draft, setDraft] = useState<ReaderPreferences | null>(null);
  const lastLoaded = useRef<ReaderPreferences | null>(null);

  useEffect(() => {
    if (!preferences.data) return;

    const previous = lastLoaded.current;
    const loaded = preferences.data;
    lastLoaded.current = loaded;
    setDraft((current) => {
      if (!current || !previous) return loaded;
      // Preserve unsaved choices if another control refreshes the account settings.
      return {
        contentLanguage: current.contentLanguage === previous.contentLanguage ? loaded.contentLanguage : current.contentLanguage,
        minSeverity: current.minSeverity === previous.minSeverity ? loaded.minSeverity : current.minSeverity,
        colorScheme: current.colorScheme === previous.colorScheme ? loaded.colorScheme : current.colorScheme,
      };
    });
  }, [preferences.data]);

  function updateDraft(changes: Partial<ReaderPreferences>) {
    save.reset();
    setDraft((current) => current ? { ...current, ...changes } : current);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (draft) save.mutate(draft);
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">{t.eyebrow}</p>
      <h1 className="mt-3 text-3xl font-bold sm:text-4xl">{t.title}</h1>
      <p className="mt-3 max-w-2xl text-base-content/65">{t.body}</p>

      {preferences.isPending && <div className="skeleton mt-8 h-72 w-full rounded-box" aria-label={t.loading} />}
      {preferences.error instanceof AccountApiError && preferences.error.status === 401 && (
        <section className="mt-8 rounded-box border border-base-300 bg-base-200 p-6">
          <h2 className="text-xl font-semibold">{t.signInTitle}</h2>
          <p className="mt-2 text-base-content/65">{t.signInBody}</p>
          <Link className="btn btn-primary mt-4" to={to("/sign-in", `?returnTo=${encodeURIComponent(`${location.pathname}${location.search}`)}`)}>{t.signIn}</Link>
        </section>
      )}
      {preferences.isError && !(preferences.error instanceof AccountApiError && preferences.error.status === 401) && (
        <div className="alert alert-error mt-8"><span>{t.loadError}</span><button className="btn btn-sm" type="button" onClick={() => preferences.refetch()}>{t.retry}</button></div>
      )}

      {preferences.isSuccess && draft && (
        <form className="mt-8 rounded-box border border-base-300 bg-base-200 p-5 sm:p-7" onSubmit={submit}>
          <div className="flex items-center gap-3">
            <Settings2 className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold">{t.accountSettings}</h2>
          </div>
          <p className="mt-2 text-sm text-base-content/60">{t.accountSettingsBody}</p>

          <ChoiceGroup
            label={t.contentLanguage}
            hint={t.contentLanguageHint}
            value={draft.contentLanguage}
            options={[["zh-Hant", t.traditionalChinese], ["en", t.english]]}
            onChange={(contentLanguage: ContentLanguage) => updateDraft({ contentLanguage })}
          />
          <ChoiceGroup
            label={t.minSeverity}
            hint={t.minSeverityHint}
            value={draft.minSeverity}
            options={[["C", t.severityAll], ["B", t.severityWatch], ["A", t.severityHigh], ["S", t.severityMajor]]}
            onChange={(minSeverity: Severity) => updateDraft({ minSeverity })}
          />
          <ChoiceGroup
            label={t.colorScheme}
            hint={t.colorSchemeHint}
            value={draft.colorScheme}
            options={[["system", t.system], ["light", t.light], ["dark", t.dark]]}
            onChange={(colorScheme: ColorSchemePreference) => updateDraft({ colorScheme })}
          />

          {save.isError && <p className="mt-5 text-sm text-error" role="alert">{t.saveError}</p>}
          {save.isSuccess && <p className="mt-5 text-sm text-success" role="status">{t.saved}</p>}
          <button className="btn btn-primary mt-6" type="submit" disabled={save.isPending || samePreferences(draft, preferences.data)}>
            <Save className="h-4 w-4" />{save.isPending ? t.saving : t.save}
          </button>
        </form>
      )}
    </div>
  );
}

function ChoiceGroup<Value extends string>({
  label,
  hint,
  value,
  options,
  onChange
}: {
  label: string;
  hint: string;
  value: Value;
  options: [Value, string][];
  onChange(value: Value): void;
}) {
  return (
    <fieldset className="mt-7">
      <legend className="font-semibold">{label}</legend>
      <p className="mt-1 text-sm text-base-content/55">{hint}</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {options.map(([option, text]) => (
          <label key={option} className={`flex cursor-pointer items-center gap-3 rounded-field border p-3 ${value === option ? "border-primary bg-primary/10" : "border-base-300 bg-base-100"}`}>
            <input className="radio radio-primary radio-sm" type="radio" name={label} checked={value === option} onChange={() => onChange(option)} />
            <span>{text}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function samePreferences(left: ReaderPreferences, right: ReaderPreferences): boolean {
  return left.contentLanguage === right.contentLanguage
    && left.minSeverity === right.minSeverity
    && left.colorScheme === right.colorScheme;
}
