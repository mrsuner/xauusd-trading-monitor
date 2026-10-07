import { BookOpen, Bookmark, Layers, Smartphone } from "lucide-react";
import { useI18n } from "../i18n";

function AppScreenshot({ label, src, priority = false }: { label: string; src: string; priority?: boolean }) {
  return (
    <figure>
      <img src={src} alt={label} width="1206" height="2622" loading={priority ? "eager" : "lazy"} fetchPriority={priority ? "high" : "auto"} className="w-full rounded-[2rem] border border-base-content/15 bg-base-200 shadow-xl" />
    </figure>
  );
}

function DownloadButtons() {
  return (
    <div className="flex flex-wrap gap-3">
      {["App Store", "Google Play"].map((store) => (
        <button key={store} type="button" disabled className="flex min-w-40 cursor-not-allowed items-center gap-3 rounded-box border border-base-content/20 bg-base-200 px-5 py-3 text-left text-base-content">
          <Smartphone className="h-5 w-5 shrink-0" aria-hidden="true" />
          <span><span className="block text-xs text-base-content/70">Coming soon</span><span className="block whitespace-nowrap text-base font-semibold">{store}</span></span>
        </button>
      ))}
    </div>
  );
}

export function AppPage() {
  const { app: t } = useI18n();
  const features = [
    { icon: BookOpen, title: t.feedTitle, body: t.feedBody },
    { icon: Layers, title: t.sourcesTitle, body: t.sourcesBody },
    { icon: Bookmark, title: t.readerTitle, body: t.readerBody },
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <section className="grid items-center gap-10 py-12 md:grid-cols-[1.2fr_0.8fr] md:gap-14 lg:py-16" aria-labelledby="app-title">
        <div>
          <p className="mb-5 text-sm font-semibold text-primary">TheTickBase News App</p>
          <h1 id="app-title" className="max-w-xl text-4xl font-bold leading-tight tracking-tight lg:text-5xl">{t.title}</h1>
          <p className="mb-8 mt-5 max-w-lg text-lg leading-relaxed text-base-content/75">{t.body}</p>
          <DownloadButtons />
        </div>
        <div className="mx-auto w-full max-w-64 md:max-w-72"><AppScreenshot label={t.feedAlt} src="/app/feed.png" priority /></div>
      </section>

      <section className="border-t border-base-content/10 py-12 lg:py-16" aria-labelledby="app-features">
        <h2 id="app-features" className="text-2xl font-semibold tracking-tight sm:text-3xl">{t.featuresTitle}</h2>
        <div className="mt-8 grid gap-8 md:grid-cols-[1.2fr_1fr]">
          <div className="rounded-box bg-base-200 p-6 sm:p-8">
            <BookOpen className="mb-5 h-6 w-6 text-primary" aria-hidden="true" />
            <h3 className="text-xl font-semibold">{features[0].title}</h3>
            <p className="mt-3 max-w-md leading-7 text-base-content/75">{features[0].body}</p>
          </div>
          <div className="grid gap-7 py-2">
            {features.slice(1).map(({ icon: Icon, title, body }) => (
              <div key={title} className="flex gap-4">
                <Icon className="mt-1 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
                <div><h3 className="text-lg font-semibold">{title}</h3><p className="mt-2 leading-7 text-base-content/75">{body}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid items-center gap-8 border-t border-base-content/10 py-12 md:grid-cols-[0.8fr_1.2fr] lg:py-16" aria-labelledby="app-digests">
        <div className="order-2 mx-auto w-full max-w-64 md:order-1"><AppScreenshot label={t.digestAlt} src="/app/digest.png" /></div>
        <div className="order-1 md:order-2">
          <span className="badge badge-outline mb-4 font-semibold">News Pro</span>
          <h2 id="app-digests" className="text-2xl font-semibold tracking-tight sm:text-3xl">{t.digestTitle}</h2>
          <p className="mt-4 max-w-lg text-lg leading-relaxed text-base-content/75">{t.digestBody}</p>
          <p className="mt-5 max-w-lg text-sm leading-6 text-base-content/70">{t.proNote}</p>
        </div>
      </section>

      <section className="border-t border-base-content/10 py-12 lg:py-16" aria-labelledby="app-download">
        <h2 id="app-download" className="text-2xl font-semibold tracking-tight sm:text-3xl">{t.downloadTitle}</h2>
        <p className="mb-6 mt-4 max-w-2xl leading-7 text-base-content/75">{t.languagesBody}</p>
        <DownloadButtons />
      </section>
    </div>
  );
}
