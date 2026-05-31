import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { StatusBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Score, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

export function Processing() {
  const [status, setStatus] = useState("");
  const query = useQuery({
    queryKey: ["processing", status],
    queryFn: () => api.processing({ page_size: 75, status }),
    refetchInterval: 15000
  });

  return (
    <>
      <PageHeader title="Processing" description="Normalizer-classifier queue state and model output status." />
      <select className="select select-bordered select-sm mb-4 w-56" value={status} onChange={(event) => setStatus(event.target.value)}>
        <option value="">All statuses</option>
        <option value="pending">pending</option>
        <option value="running">running</option>
        <option value="completed">completed</option>
        <option value="skipped">skipped</option>
        <option value="failed">failed</option>
        <option value="retry">retry</option>
      </select>
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm">
          <thead>
            <tr>
              <th className="w-32">Updated</th>
              <th className="w-40">Source</th>
              <th>Item</th>
              <th className="w-28">Stage</th>
              <th className="w-28">Status</th>
              <th className="w-20">Score</th>
              <th className="w-32">Model</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <LoadingRows columns={7} /> : null}
            {query.data?.items.length === 0 ? <EmptyRow columns={7}>No processing tasks found.</EmptyRow> : null}
            {query.data?.items.map((item) => (
              <tr key={item.id}>
                <td>{formatTime(item.updated_at)}</td>
                <td><Truncate text={item.source_name} /></td>
                <td><Truncate className="font-medium" text={item.title || item.raw_item_id} /><Truncate className="text-xs text-error" text={item.error_message} /></td>
                <td>{item.stage}</td>
                <td><StatusBadge value={item.status} /></td>
                <td><Score value={item.relevance_score} /></td>
                <td><Truncate text={item.model_name || item.model_provider} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
