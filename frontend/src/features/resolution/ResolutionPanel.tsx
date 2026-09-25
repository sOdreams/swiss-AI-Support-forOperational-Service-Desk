import { ArrowRight, ClipboardList, MessageSquare, SearchCheck } from "lucide-react";
import type { ActionReview, ResolutionEdits, ResolutionResponse } from "../../types/resolution";

export function ResolutionPanel({ data, review, loading, error, enabled, onRun, onReviewChange, outcome, onOutcomeChange }: {
  data: ResolutionResponse | null; review: ResolutionEdits | null; loading: boolean; error: string | null;
  enabled: boolean; onRun: () => void; onReviewChange: (review: ResolutionEdits) => void;
  outcome: string; onOutcomeChange: (value: string) => void;
}) {
  const proposal = data?.resolution.status === "ready" ? data.resolution : null;
  const decide = (id: string, decision: ActionReview["decision"], original: string) => {
    if (!review) return;
    onReviewChange({ ...review, actions: review.actions.map((action) => action.action_id === id
      ? { ...action, decision, edited_next_step: decision === "edit" ? action.edited_next_step ?? original : null } : action) });
  };

  return <section className="processor-section" aria-label="Resolution assistance">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="flex items-center gap-2 font-semibold"><ClipboardList className="h-4 w-4 text-teal-700" />Next steps for your review</h3>
        <p className="mt-1 text-xs text-slate-600">Evidence-backed actions, one useful question and a reply you can edit.</p></div>
      <button type="button" onClick={onRun} disabled={!enabled || loading}
        className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Preparing next steps…" : "Generate next steps"}</button>
    </div>
    {!enabled && <p className="mt-3 text-xs text-slate-500">Run Clean & filter to prepare the evidence first.</p>}
    {loading && <p role="status" className="mt-3 text-sm text-slate-600">Preparing suggestions from the selected evidence…</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}. You can still record your own findings.</p>}
    {data?.resolution.status === "unavailable" && <p role="alert" className="mt-3 text-sm text-amber-800">{data.resolution.reason}</p>}
    {proposal && review && <>
      <p className="mt-3 text-xs text-slate-500">{data?.cache_hit ? "Reused recent suggestions" : "New suggestions"} · {proposal.mode === "needs_information" ? "Clarification needed" : "Ready for analyst review"}</p>
      {proposal.critical_question && <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <h4 className="text-xs font-bold uppercase tracking-wide text-amber-900">One critical question</h4>
        <p className="mt-2 text-sm text-slate-800">{proposal.critical_question}</p>
      </div>}
      <div className="mt-4 space-y-3">{proposal.actions.map((action, index) => {
        const choice = review.actions.find((item) => item.action_id === action.id)!;
        const checks = [...new Set([...(action.check_first ? [action.check_first] : []), ...action.required_checks])];
        return <article key={action.id} aria-label={`Action ${index + 1}`}
          className={`rounded-xl border p-4 ${choice.decision === "not_applicable" ? "border-slate-200 bg-slate-50" : "border-teal-200 bg-white"}`}>
          <div className="flex items-center justify-between gap-2 text-xs"><span className="font-bold text-teal-800">{String(index + 1).padStart(2, "0")} · {action.kind === "procedure" ? "Suggested procedure" : "Diagnostic check"}</span>
            <span className="text-slate-500">{choice.decision === "unreviewed" ? "Not reviewed" : choice.decision === "not_applicable" ? "Not applicable" : choice.decision === "edit" ? "Edited" : "Selected"}</span></div>
          <h4 className="mt-3 text-xs font-semibold text-slate-500">Recommended next step</h4>
          {choice.decision === "edit" ? <textarea aria-label={`Edit action ${index + 1}`} rows={3}
            className="mt-1 w-full rounded-lg border border-teal-300 p-2 text-sm" value={choice.edited_next_step ?? action.next_step}
            onChange={(event) => onReviewChange({ ...review, actions: review.actions.map((item) => item.action_id === action.id ? { ...item, edited_next_step: event.target.value } : item) })} />
            : <p className="mt-1 text-sm font-semibold text-slate-900">{action.next_step}</p>}
          <p className="mt-2 text-xs leading-5 text-slate-600"><span className="font-semibold">Why this next step: </span>{action.reason}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg bg-amber-50 p-3"><h5 className="text-xs font-semibold text-amber-900">Check first</h5>
              {checks.length ? <ul className="mt-1 ml-4 list-disc space-y-1 text-xs leading-5 text-slate-700">{checks.map((check) => <li key={check}>{check}</li>)}</ul>
                : <p className="mt-1 text-xs text-slate-600">Prerequisites are not established by the available evidence.</p>}</div>
            <div className="rounded-lg bg-slate-50 p-3"><h5 className="flex items-center gap-1 text-xs font-semibold text-slate-700"><SearchCheck className="h-3.5 w-3.5" />Expected outcome</h5>
              <p className="mt-1 text-xs leading-5 text-slate-600">{action.expected_outcome ?? "A verification criterion is not established by the available evidence."}</p></div>
          </div>
          <details className="mt-3 text-xs"><summary className="cursor-pointer font-medium text-teal-800">Source · {action.sources.length} references</summary>
            {action.sources.map((source) => <div key={source.id} className="mt-2 border-l-2 border-teal-200 pl-3">
              <p className="font-semibold text-slate-600">{source.id} · {source.kind.replaceAll("_", " ")}{source.source ? ` · ${source.source}` : ""}</p>
              <p className="mt-1 whitespace-pre-wrap leading-5 text-slate-700">{source.text}</p>
              {source.verification_excerpt && <p className="mt-2 rounded bg-slate-50 p-2 text-slate-700"><span className="font-semibold">Historical verification: </span>{source.verification_excerpt}<span className="mt-1 block text-slate-500">Past evidence, not confirmation of the current outcome.</span></p>}
              {source.original_rank && <p className="text-slate-500">Original rank {source.original_rank}</p>}
              {source.sources && <p className="text-slate-500">Original ranks: {source.sources.map((s) => s.original_rank).join(", ")}</p>}
            </div>)}
          </details>
          <div className="mt-4 flex flex-wrap gap-2">{([ ["use", "Use"], ["edit", "Edit"], ["not_applicable", "Not applicable"] ] as const).map(([decision, label]) =>
            <button key={decision} type="button" aria-pressed={choice.decision === decision} onClick={() => decide(action.id, decision, action.next_step)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${choice.decision === decision ? "border-teal-700 bg-teal-700 text-white" : "border-slate-300 bg-white text-slate-700"}`}>{label}</button>)}
          </div>
        </article>;
      })}</div>
      <div className="mt-4 rounded-xl bg-slate-50 p-4"><label htmlFor="resolution-reply" className="flex items-center gap-2 text-sm font-semibold"><MessageSquare className="h-4 w-4 text-teal-700" />Reply draft</label>
        <textarea id="resolution-reply" rows={4} className="mt-2 w-full rounded-lg border border-slate-300 bg-white p-3 text-sm leading-6"
          value={review.reply_draft} onChange={(event) => onReviewChange({ ...review, reply_draft: event.target.value })} />
        <p className="mt-1 text-xs text-slate-500">Editable draft. Nothing is sent to the requester automatically.</p>
      </div>
      <div className="mt-4"><label htmlFor="resolution-outcome" className="flex items-center gap-2 text-sm font-semibold"><ArrowRight className="h-4 w-4 text-teal-700" />Actual action and outcome</label>
        <textarea id="resolution-outcome" rows={3} value={outcome} onChange={(event) => onOutcomeChange(event.target.value)}
          className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm" placeholder="Record what you actually did, what you observed, and anything still unresolved." />
        <p className="mt-1 text-xs text-slate-500">Required to save this review. Selecting Use records your choice; it does not execute a step or confirm success.</p>
      </div>
    </>}
  </section>;
}
