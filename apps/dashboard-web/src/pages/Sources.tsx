import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { OfficialBadge, PriorityBadge, StatusBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Score, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

export function Sources() {
  const [sourceType, setSourceType] = useState("");
  const sources = useQuery({
    queryKey: ["sources", sourceType],
    queryFn: () => api.sources({ page_size: 100, source_type: sourceType }),
    refetchInterval: 60000
  });
  const health = useQuery({
    queryKey: ["source-health"],
    queryFn: () => api.sourceHealth({ page_size: 200 }),
    refetchInterval: 30000
  });
  const healthBySource = new Map(health.data?.items.map((item) => [item.source_id, item]));

  return (
    <>
      <PageHeader title="Sources" description="Source registry and collector health." />
      <div className="mb-4 w-64">
        <select className="select select-bordered select-sm w-full" value={sourceType} onChange={(event) => setSourceType(event.target.value)}>
          <option value="">All source types</option>
          <option value="telegram">telegram</option>
          <option value="rss">rss</option>
          <option value="html_polling">html_polling</option>
        </select>
      </div>
      {sources.error ? <ErrorPanel error={sources.error} /> : null}
      {health.error ? <ErrorPanel error={health.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm">
          <thead>
            <tr>
              <th className="w-64">Source</th>
              <th className="w-32">Type</th>
              <th className="w-40">Group</th>
              <th className="w-32">Official</th>
              <th className="w-24">Priority</th>
              <th className="w-24">Score</th>
              <th className="w-32">Health</th>
              <th className="w-32">Last Success</th>
            </tr>
          </thead>
          <tbody>
            {sources.isLoading ? <LoadingRows columns={8} /> : null}
            {sources.data?.items.length === 0 ? <EmptyRow columns={8}>No sources found.</EmptyRow> : null}
            {sources.data?.items.map((source) => {
              const sourceHealth = healthBySource.get(source.id);
              return (
                <tr key={source.id}>
                  <td><Truncate className="font-medium" text={source.name} /><Truncate className="text-xs text-base-content/55" text={source.handle_or_url} /></td>
                  <td>{source.source_type}</td>
                  <td><Truncate text={source.source_group} /></td>
                  <td><OfficialBadge value={source.official_level} /></td>
                  <td><PriorityBadge value={source.priority} /></td>
                  <td><Score value={source.reliability_score} /></td>
                  <td><StatusBadge value={source.enabled ? sourceHealth?.status || "unknown" : "disabled"} /></td>
                  <td>{formatTime(sourceHealth?.last_success_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
