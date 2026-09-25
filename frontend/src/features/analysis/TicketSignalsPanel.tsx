import { CheckCircle2, CircleHelp, Info, TriangleAlert } from "lucide-react";
import type { CurrentEvidence, FilterResult, SignalKind } from "../../types/analysis";

const labels: Record<SignalKind, string> = {
  last_known_good: "Reported working step", first_observed_failure: "Observed failure",
  change_event: "Preceding change", blocked_outcome: "Blocked business outcome", scope: "Affected scope",
  workaround: "Available workaround", deadline: "Reported deadline", constraint: "Explicit constraints",
};
const supportLabels = {
  procedure_reference: "Historical procedure references available", analogue_only: "Similar cases only",
  no_selected_evidence: "No applicable evidence selected", unavailable: "Evidence assessment unavailable",
  needs_review: "Evidence needs clarification or review",
};

function EvidenceQuotes({ evidence }: { evidence: CurrentEvidence[] }) {
  return <details className="mt-2 text-xs text-slate-600"><summary className="cursor-pointer">Current evidence</summary>
    {evidence.map((quote) => <blockquote key={quote.fact_id} className="mt-2 border-l-2 border-slate-300 pl-2">
      <span className="font-medium">{quote.fact_id} · {quote.source}</span><p className="mt-1">{quote.text}</p>
    </blockquote>)}
  </details>;
}

export function TicketSignalsPanel({ filter }: { filter: FilterResult | null | undefined }) {
  if (!filter?.signals && !filter?.evidence_support) return null;
  const signals = filter.signals;
  const support = filter.evidence_support;
  return <section className="processor-section" aria-label="Situation and known checks">
    <h3 className="flex items-center gap-2 font-semibold"><Info className="h-4 w-4 text-blue-700" />Situation and known checks</h3>
    <p className="mt-1 text-xs text-slate-600">Current observations and prerequisites, with the original evidence for review.</p>
    {filter.status === "needs_review" && <p role="status" className="mt-3 text-sm text-amber-800">Review the conflicting service interpretations before using these suggestions.</p>}
    {signals && <>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">{signals.observations.map((item) =>
        <article key={item.kind} aria-label={labels[item.kind]} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
          <h4 className="text-xs font-semibold text-slate-600">{labels[item.kind]}</h4>
          <p className="mt-1 text-sm text-slate-900">{item.text}</p><EvidenceQuotes evidence={item.evidence} />
        </article>)}</div>
      {signals.prerequisites.length > 0 && <div className="mt-4"><h4 className="text-sm font-semibold">What is already known</h4>
        <ul className="mt-2 space-y-2">{signals.prerequisites.map((item) => <li key={item.check} className="rounded-lg border border-slate-200 p-3">
          <div className="flex items-start gap-2">
            {item.state === "satisfied" ? <CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-teal-700" />
              : item.state === "contradicted" ? <TriangleAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-red-700" />
                : <CircleHelp aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />}
            <div><p className="text-sm">{item.check}</p><p className="mt-1 text-xs font-medium text-slate-600">{item.state === "satisfied" ? "Already established in the ticket" : item.state === "contradicted" ? "Contradicted by current evidence" : "Not established; confirm if needed for the next step"}</p>
              <EvidenceQuotes evidence={item.evidence} /></div>
          </div>
        </li>)}</ul>
      </div>}
      {!signals.observations.length && !signals.prerequisites.length && <p className="mt-3 text-xs text-slate-500">No additional current signals were established.</p>}
    </>}
    {support && <div className={`mt-4 rounded-lg border p-3 ${support.state === "procedure_reference" ? "border-teal-200 bg-teal-50" : "border-amber-200 bg-amber-50"}`}>
      <h4 className="text-sm font-semibold">{supportLabels[support.state]}</h4><p className="mt-1 text-xs leading-5">{support.reason}</p>
      <p className="mt-1 text-xs text-slate-500">Assessment of the retrieved candidates; it does not establish current recovery.</p>
    </div>}
  </section>;
}
