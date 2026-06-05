import { PageHeader } from "../components/PageHeader";
import { useI18n } from "../i18n";

export function AboutPage() {
  const t = useI18n();

  return (
    <>
      <PageHeader
        eyebrow={t.about.eyebrow}
        title={t.about.title}
        body={t.about.body}
      />
      <section className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="space-y-8">
          {t.about.sections.map((section) => (
            <section key={section.title}>
              <h2 className="text-xl font-semibold">{section.title}</h2>
              <p className="mt-3 leading-7 text-base-content/70">{section.body}</p>
            </section>
          ))}
        </div>
      </section>
    </>
  );
}
