import type { RetrievalResponse } from "../../types/retrieval";

export function RetrievalEvidencePanel({ data, loading, error, selectedIds, onToggle }: {
  data: RetrievalResponse | null;
  loading: boolean;
  error: string | null;
  selectedIds: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <section className="processor-section" aria-label="Historical evidence">
      <div className="processor-section-heading">
        <div><h3>Historical evidence · Top 50</h3><p>Review similar cases before choosing a solution. Comments are aggregated across historical tickets.</p></div>
      </div>
      {loading && <p role="status" className="text-sm text-slate-600">Searching historical tickets…</p>}
      {error && <p role="alert" className="text-sm text-red-700">Historical evidence unavailable: {error}. You can still record the actual solution.</p>}
      {data && data.hits.length === 0 && <p className="text-sm text-slate-600">No historical evidence found.</p>}
      {data?.hits.map((hit) => (
        <details key={hit.document_id} className="my-2 rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold">{hit.rank}. {hit.summary}
            <span className="ml-2 text-xs font-normal text-slate-500">Similarity {hit.score.toFixed(3)} · {hit.historical_count} historical tickets</span>
          </summary>
          <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-700">{hit.matched_text}</p>
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer">Original comments and source examples</summary>
            {hit.evidence.map((evidence, index) => (
              <div key={index} className="mt-2 border-t border-slate-100 pt-2">
                <p className="whitespace-pre-wrap">{evidence.body}</p>
                <p className="mt-1 text-slate-500">{evidence.occurrences} occurrences; showing up to 3 original sources:</p>
                <ul className="ml-4 list-disc text-slate-500">{evidence.sources.map((source) => (
                  <li key={`${source.row_index}-${source.comment_index}`}>{source.ticket_id}, comment {source.comment_index + 1} · {source.author ?? "Unknown author"} · {source.services.join(", ") || "Unknown service"}</li>
                ))}</ul>
              </div>
            ))}
          </details>
          <label className="mt-3 flex items-center gap-2 text-xs font-medium">
            <input type="checkbox" checked={selectedIds.includes(hit.document_id)} onChange={() => onToggle(hit.document_id)} />
            Used this evidence in my review
          </label>
        </details>
      ))}
      {data && <p className="mt-2 text-xs text-slate-500">Similarity is not confidence. Historical authors and teams are evidence, not routing assignments.</p>}
    </section>
  );
}
