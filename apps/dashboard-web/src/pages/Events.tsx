import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { SeverityBadge, OfficialBadge, PriorityBadge } from "../components/Badges";
import { EmptyRow, ErrorPanel, LoadingRows } from "../components/DataState";
import { formatTime, Score, Truncate } from "../components/Format";
import { PageHeader } from "../components/Layout";

export function Events() {
  const [severity, setSeverity] = useState("");
  const query = useQuery({
    queryKey: ["events", severity],
    queryFn: () => api.events({ page_size: 50, severity }),
    refetchInterval: 30000
  });

  return (
    <>
      <PageHeader title="Events" description="High relevance events created by normalizer-classifier." />
      <div className="mb-4 max-w-full overflow-x-auto">
        <div className="tabs tabs-box w-fit">
        {["", "S", "A", "B", "C"].map((item) => (
          <button key={item || "all"} className={`tab ${severity === item ? "tab-active" : ""}`} onClick={() => setSeverity(item)}>
            {item || "All"}
          </button>
        ))}
        </div>
      </div>
      {query.error ? <ErrorPanel error={query.error} /> : null}
      <div className="overflow-x-auto rounded border border-base-300 bg-base-100">
        <table className="table table-sm min-w-[860px]">
          <thead>
            <tr>
              <th className="w-32">Time</th>
              <th className="w-16">Severity</th>
              <th className="w-40">Type</th>
              <th>Title</th>
              <th className="w-32">Source</th>
              <th className="w-24">Score</th>
              <th className="w-24">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {query.isLoading ? <LoadingRows columns={7} /> : null}
            {query.data?.items.length === 0 ? <EmptyRow columns={7}>No events in selected range.</EmptyRow> : null}
            {query.data?.items.map((event) => (
              <tr key={event.id}>
                <td>{formatTime(event.detected_at)}</td>
                <td><SeverityBadge value={event.severity} /></td>
                <td><Truncate text={event.event_type} /></td>
                <td>
                  <Link className="link link-primary font-medium" to={`/events/${event.id}`}>
                    <Truncate text={event.title || event.summary_zh} />
                  </Link>
                  <Truncate className="text-xs text-base-content/55" text={event.summary_zh} />
                </td>
                <td>
                  <Truncate text={event.source_name || event.source_group} />
                  <div className="mt-1 flex gap-1"><OfficialBadge value={event.official_level} /><PriorityBadge value={event.priority} /></div>
                </td>
                <td><Score value={event.relevance_score} /></td>
                <td><Score value={event.confidence} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
