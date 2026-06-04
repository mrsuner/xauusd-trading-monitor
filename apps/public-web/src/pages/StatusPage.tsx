import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { getHealth, getOverviewStats } from "../api/client";
import { ErrorState, LoadingState } from "../components/DataState";
import { PageHeader } from "../components/PageHeader";
import { StatsStrip } from "../components/StatsStrip";

export function StatusPage() {
  const healthQuery = useQuery({ queryKey: ["public-health"], queryFn: getHealth, refetchInterval: 60_000 });
  const statsQuery = useQuery({ queryKey: ["public-stats"], queryFn: getOverviewStats, staleTime: 30_000 });

  return (
    <>
      <PageHeader
        eyebrow="Status"
        title="Public API Status"
        body="公共網站只依賴 VPS public-api。此頁顯示公開 API 與 public database 的基本健康狀態。"
        aside={<StatsStrip stats={statsQuery.data} />}
      />
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {healthQuery.isLoading && <LoadingState label="Checking public API..." />}
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
                  API: {healthQuery.data.status}; database: {healthQuery.data.database ?? "unknown"}
                </p>
              </div>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
