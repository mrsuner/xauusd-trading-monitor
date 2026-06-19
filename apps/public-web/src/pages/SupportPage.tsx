import { Coffee, Heart } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useI18n } from "../i18n";

export const KOFI_URL = "https://ko-fi.com/alphablue";

export function SupportPage() {
  const t = useI18n();

  return (
    <>
      <PageHeader
        eyebrow={t.support.eyebrow}
        title={t.support.title}
        body={t.support.body}
      />
      <section className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="space-y-10">
          <div>
            <h2 className="text-xl font-semibold">{t.support.costsTitle}</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {t.support.costs.map((cost) => (
                <div
                  key={cost.title}
                  className="rounded-box border border-base-300/60 bg-base-200/60 p-4"
                >
                  <h3 className="text-sm font-semibold">{cost.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-base-content/65">{cost.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-box border border-primary/30 bg-primary/5 p-6">
            <h2 className="flex items-center gap-2 text-xl font-semibold">
              <Heart className="h-5 w-5 text-primary" />
              {t.support.ctaTitle}
            </h2>
            <p className="mt-3 leading-7 text-base-content/70">{t.support.ctaBody}</p>
            <a
              href={KOFI_URL}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary mt-5"
            >
              <Coffee className="h-4 w-4" />
              {t.support.ctaButton}
            </a>
            <p className="mt-4 text-xs leading-5 text-base-content/55">{t.support.ctaNote}</p>
          </div>

          <p className="text-sm leading-6 text-base-content/55">{t.support.disclaimer}</p>
        </div>
      </section>
    </>
  );
}
