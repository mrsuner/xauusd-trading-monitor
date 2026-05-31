import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { OfficialBadge, PriorityBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

export function Timeline() {
  const [q, setQ] = useState("");
  const [sourceGroup, setSourceGroup] = useState("");
  const query = useQuery({
    queryKey: ["raw-items", q, sourceGroup],
    queryFn: () => api.rawItems({ page_size: 75, q, source_group: sourceGroup }),
    refetchInterval: 15000
  });

  return (
    <>
      <PageHeader title="Live Timeline" description="Recent raw items from Telegram, RSS and official pages." />
      <div className="mb-4 grid gap-2 md:grid-cols-[1fr_260px]">
        <input className="input input-bordered input-sm" placeholder="Keyword search" value={q} onChange={(event) => setQ(event.target.value)} />
        <input className="input input-bordered input-sm" placeholder="source_group" value={sourceGroup} onChange={(event) => setSourceGroup(event.target.value)} />
      </div>
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm">
          <thead>
            <tr>
              <th className="w-32">Time</th>
              <th className="w-56">Source</th>
              <th>Message</th>
              <th className="w-32">Group</th>
              <th className="w-24">Priority</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <LoadingRows columns={5} /> : null}
            {query.data?.items.length === 0 ? <EmptyRow columns={5}>No raw items in selected range.</EmptyRow> : null}
            {query.data?.items.map((item) => (
              <tr key={item.id}>
                <td>{formatTime(item.published_at || item.ingested_at)}</td>
                <td>
                  <Truncate text={item.source_name} />
                  <div className="mt-1"><OfficialBadge value={item.official_level} /></div>
                </td>
                <td>
                  <Truncate className="font-medium" text={item.summary_zh || item.title || item.text_clean || item.text_raw} />
                  <Truncate className="text-xs text-base-content/55" text={item.url} />
                </td>
                <td><Truncate text={item.source_group} /></td>
                <td><PriorityBadge value={item.priority} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
