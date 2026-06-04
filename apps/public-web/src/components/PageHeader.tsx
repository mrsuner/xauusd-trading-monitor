import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  body,
  aside
}: {
  eyebrow: string;
  title: string;
  body: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <section className="border-b border-base-300/60 bg-base-100 bg-grid">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[1fr_auto] lg:px-8">
        <div>
          <p className="font-mono text-xs uppercase text-primary">{eyebrow}</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
          <div className="mt-3 max-w-3xl text-sm leading-6 text-base-content/65 sm:text-base">{body}</div>
        </div>
        {aside && <div className="lg:min-w-72">{aside}</div>}
      </div>
    </section>
  );
}
