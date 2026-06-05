import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { getHealth, getOverviewStats } from "../api/client";
import { ErrorState, LoadingState } from "../components/DataState";
import { PageHeader } from "../components/PageHeader";
import { StatsStrip } from "../components/StatsStrip";
import { useI18n } from "../i18n";

export function StatusPage() {
  const t = useI18n();
  const healthQuery = useQuery({ queryKey: ["public-health"], queryFn: getHealth, refetchInterval: 60_000 });
  const statsQuery = useQuery({ queryKey: ["public-stats"], queryFn: getOverviewStats, staleTime: 30_000 });

  return (
    <>
      <PageHeader
        eyebrow={t.status.eyebrow}
        title={t.status.title}
        body={t.status.body}
        aside={<StatsStrip stats={statsQuery.data} />}
      />
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {healthQuery.isLoading && <LoadingState label={t.status.loading} />}
        {healthQuery.isError && <ErrorState message={(healthQuery.error as Error).message} />}
        {healthQuery.data && (
          <div className="rounded-box border border-base-300 bg-base-200/40 p-5">
            <div className="flex items-start gap-3">
              {healthQuery.data.status === "ok" ? (
                <CheckCircle2 className="mt-0.5 h-5 w-5 text-success" />
              ) : (
                <XCircle className="mt-0.5 h-5 w-5 text-error" />
              )}
              <div>
                <h2 className="font-semibold">{healthQuery.data.service}</h2>
                <p className="mt-1 text-sm text-base-content/60">
                  {t.status.api}: {healthQuery.data.status}; {t.status.database}:{" "}
                  {healthQuery.data.database ?? t.status.unknown}
                </p>
              </div>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
