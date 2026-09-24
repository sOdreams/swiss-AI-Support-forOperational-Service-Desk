import type { RetrievalResponse } from "../../types/retrieval";
import type { FilterResult } from "../../types/analysis";
import { useState } from "react";

export function RetrievalEvidencePanel({ data, loading, error, selectedIds, onToggle, filter }: {
  data: RetrievalResponse | null;
  loading: boolean;
  error: string | null;
  selectedIds: string[];
  onToggle: (id: string) => void;
  filter?: FilterResult | null;
}) {
  const [showAll, setShowAll] = useState(false);
  const filtered = filter?.status === "ready";
  const hits = data?.hits.filter((hit) => !filtered || showAll || filter.primary_document_ids.includes(hit.document_id));
  const activeComments = filter?.comments.filter((comment) => filter.active_comment_ids.includes(comment.id)) ?? [];
  return (
    <section className="processor-section" aria-label="Historical evidence">
      <div className="processor-section-heading">
        <div><h3>Historical evidence · Top 50</h3><p>Review similar cases before choosing a solution. Comments are aggregated across historical tickets.</p></div>
      </div>
      {loading && <p role="status" className="text-sm text-slate-600">Searching historical tickets…</p>}
      {error && <p role="alert" className="text-sm text-red-700">Historical evidence unavailable: {error}. You can still record the actual solution.</p>}
      {data && data.hits.length === 0 && <p className="text-sm text-slate-600">No historical evidence found.</p>}
      {filter?.status === "unfiltered_fallback" && <p role="status" className="text-sm text-amber-800">Filtering unavailable; showing original retrieval for review.</p>}
      {filter?.status === "needs_review" && <p role="status" className="text-sm text-amber-800">Service interpretations disagree; candidate selections are held for review. Showing original retrieval.</p>}
      {filtered && <div className="my-3 text-sm"><p>{filter.reason}</p>
        <button type="button" onClick={() => setShowAll(!showAll)} className="mt-2 rounded border border-slate-300 px-3 py-1">{showAll ? `Show ${filter.primary_document_ids.length} primary candidates` : `Show all ${data?.hits.length ?? 0} candidates`}</button>
        {!showAll && !hits?.length && <p className="mt-2 text-amber-800">No supported primary analogue. Review the original candidates or clarify the ticket.</p>}
      </div>}
      {filtered && activeComments.length > 0 && <section className="my-3 rounded-lg bg-blue-50 p-3" aria-label="Selected historical comments">
        <h4 className="text-sm font-semibold">Selected historical references</h4><p className="text-xs text-slate-600">Verify prerequisites against the current ticket before considering a historical remedy.</p>
        {activeComments.map((comment) => <div key={comment.id} className="mt-3 border-t border-blue-100 pt-2 text-xs">
          <p>{comment.text}</p><p className="mt-1 text-slate-600">{comment.reason}</p>
          {comment.condition && <p className="mt-2 font-medium text-amber-900">Check first: {comment.condition}</p>}
          <p className="mt-1 text-slate-500">Source ranks: {comment.sources.map((source) => source.original_rank).join(", ")} · {comment.status}</p>
        </div>)}
      </section>}
      {hits?.map((hit) => (
        <details key={hit.document_id} className="my-2 rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold">{hit.rank}. {hit.summary}
            <span className="ml-2 text-xs font-normal text-slate-500">Similarity {hit.score.toFixed(3)} · {hit.historical_count} historical tickets</span>
          </summary>
          {filtered && <p className="mt-2 text-xs font-medium text-blue-800">{filter.candidates.find((candidate) => candidate.document_id === hit.document_id)?.role.replace("_", " ")} · original rank {hit.rank}</p>}
          <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-700">{filtered ? filter.candidates.find((candidate) => candidate.document_id === hit.document_id)?.description : hit.matched_text}</p>
          {(!filtered || showAll) && <details className="mt-3 text-xs">
            <summary className="cursor-pointer">Original unfiltered comments and source examples</summary>
            {hit.evidence.map((evidence, index) => (
              <div key={index} className="mt-2 border-t border-slate-100 pt-2">
                <p className="whitespace-pre-wrap">{evidence.body}</p>
                <p className="mt-1 text-slate-500">{evidence.occurrences} occurrences; showing up to 3 original sources:</p>
                <ul className="ml-4 list-disc text-slate-500">{evidence.sources.map((source) => (
                  <li key={`${source.row_index}-${source.comment_index}`}>{source.ticket_id}, comment {source.comment_index + 1} · {source.author ?? "Unknown author"} · {source.services.join(", ") || "Unknown service"}</li>
                ))}</ul>
              </div>
            ))}
          </details>}
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
