import { Gauge, Route } from "lucide-react";
import type { TriageResult } from "../../types/triage";

export function TriagePanel({ triage }: { triage: TriageResult | undefined }) {
  if (!triage) return null;
  const { priority, routing } = triage;
  return <section className="processor-section" aria-label="Priority and routing suggestions">
    <h3 className="font-semibold">Priority and routing for review</h3>
    <div className="mt-3 grid gap-3 sm:grid-cols-2">
      <article className="rounded-xl border border-blue-200 bg-blue-50/40 p-4" aria-label="Priority assessment">
        <h4 className="flex items-center gap-2 text-sm font-semibold"><Gauge className="h-4 w-4 text-blue-700" />Suggested priority</h4>
        <p className="mt-2 text-xl font-bold text-slate-900">{priority.value ?? (priority.status === "needs_review" ? "Review disagreement" : "Not established")}</p>
        <dl className="mt-3 space-y-2 text-xs"><div><dt className="font-semibold">Urgency</dt><dd>{priority.urgency.value ?? "Unknown"}</dd></div>
          <div><dt className="font-semibold">Impact</dt><dd>{priority.impact.value ?? "Unknown"}</dd></div></dl>
        <p className="mt-3 text-xs leading-5 text-slate-600">{priority.reason}</p>
        <details className="mt-2 text-xs"><summary className="cursor-pointer font-semibold text-blue-800">Evidence and calculation</summary>
          {([ ["Urgency", priority.urgency], ["Impact", priority.impact] ] as const).map(([label, dimension]) => <div key={label} className="mt-2">
            <p className="font-semibold">{label}: {dimension.value ?? "Unknown"}</p>
            {dimension.evidence.map((e) => <blockquote key={e.fact_id} className="mt-1 border-l-2 border-blue-200 pl-2">{e.fact_id} · {e.text}</blockquote>)}
          </div>)}
          <p className="mt-2">{priority.urgency.value ?? "Unknown"} × {priority.impact.value ?? "Unknown"} → {priority.proposed_value ?? "Unknown"}{priority.status === "needs_review" ? " (on hold)" : ""}</p>
          <a className="mt-2 inline-block text-blue-700 underline" href={priority.rule_source} target="_blank" rel="noreferrer">Challenge priority matrix</a>
        </details>
      </article>
      <article className="rounded-xl border border-teal-200 bg-teal-50/40 p-4" aria-label="Routing suggestion">
        <h4 className="flex items-center gap-2 text-sm font-semibold"><Route className="h-4 w-4 text-teal-700" />Suggested receiving team</h4>
        <p className="mt-2 text-lg font-bold text-slate-900">{routing.team ?? "Needs ownership review"}</p>
        <p className="mt-1 text-xs text-slate-600">Service: {routing.service ?? "Unresolved"}</p>
        <p className="mt-3 text-xs leading-5 text-slate-600">{routing.reason}</p>
        <details className="mt-2 text-xs"><summary className="cursor-pointer font-semibold text-teal-800">Service and catalogue evidence</summary>
          {routing.service_evidence.map((e) => <blockquote key={e.fact_id} className="mt-2 border-l-2 border-teal-200 pl-2">{e.fact_id} · {e.text}</blockquote>)}
          {routing.catalogue_evidence.map((e) => <p key={e.team} className="mt-2">{e.team}: {e.historical_rows} distinct historical rows; example row indices {e.example_row_indices.join(", ")}. Index {routing.index_version}.</p>)}
        </details>
      </article>
    </div>
    {routing.historical_contributors.length > 0 && <details className="mt-3 text-xs"><summary className="cursor-pointer font-semibold">Historical contributors for this scenario</summary>
      <p className="mt-2 text-slate-500">Comment authors, not verified current assignees. Confirm team membership and availability before contacting or assigning.</p>
      {routing.historical_contributors.map((person) => <div key={person.author} className="mt-3 rounded-lg border border-slate-200 p-3">
        <p className="font-semibold">{person.author}</p>{person.evidence.map((e) => <blockquote key={e.comment_id} className="mt-2 border-l-2 pl-2">
          <p>{e.comment_id} · Original rank {e.original_rank} · Source row {e.row_index}</p><p className="mt-1">{e.text}</p>
          {e.condition && <p className="mt-1 text-amber-800">Check first: {e.condition}</p>}
        </blockquote>)}
      </div>)}
    </details>}
    <p className="mt-3 text-xs text-slate-500">Reviewable suggestions. The imported priority, team and assignee remain unchanged.</p>
  </section>;
}
