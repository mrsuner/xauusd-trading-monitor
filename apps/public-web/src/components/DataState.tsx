import { AlertTriangle, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";

export function LoadingState({ label }: { label?: string }) {
  const t = useI18n();
  return (
    <div className="flex min-h-56 items-center justify-center rounded-box border border-base-300 bg-base-200/40">
      <div className="flex items-center gap-3 text-sm text-base-content/60">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        {label ?? t.states.loading}
      </div>
    </div>
  );
}

export function EmptyState({ title, body }: { title: string; body: ReactNode }) {
  return (
    <div className="rounded-box border border-dashed border-base-300 bg-base-200/30 p-8 text-center">
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-base-content/60">{body}</p>
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  const t = useI18n();
  return (
    <div className="rounded-box border border-error/30 bg-error/10 p-5 text-error">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
        <div>
          <p className="font-semibold">{t.states.apiErrorTitle}</p>
          <p className="mt-1 text-sm opacity-80">{message}</p>
        </div>
      </div>
    </div>
  );
}
