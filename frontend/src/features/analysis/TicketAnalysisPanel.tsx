import type { FieldSuggestion, TicketAnalysisResponse } from "../../types/analysis";
import type { Ticket } from "../../types/ticket";

const labels = { summary: "Title", work_type: "Work type", affected_business_or_it_services: "Affected service" };
const states = { keep: "Keep", propose_correction: "Suggested correction", propose_completion: "Suggested completion",
  needs_clarification: "Needs clarification", needs_review: "Review disagreement" };
const display = (value: FieldSuggestion["current"]) => Array.isArray(value) ? value.join(", ") || "Not recorded" : value ?? "Unresolved";

export function TicketAnalysisPanel({ ticket, data, loading, error, onRun }: {
  ticket: Ticket; data: TicketAnalysisResponse | null; loading: boolean; error: string | null; onRun: () => void;
}) {
  const download = () => {
    if (!data) return;
    const preview = structuredClone(ticket.raw ?? ticket) as Record<string, unknown>;
    const rawNames = { summary: "Summary", work_type: "Work type", affected_business_or_it_services: "Affected Business or IT Services" };
    for (const field of data.clean.fields) {
      if (field.state === "propose_correction" || field.state === "propose_completion") {
        preview[ticket.raw ? rawNames[field.field] : field.field] = field.suggested;
      }
    }
    const url = URL.createObjectURL(new Blob([JSON.stringify({ ticket_preview: preview, analysis: data }, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = `${ticket.issue_key}-analysis.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className="processor-section" aria-label="Ticket cleaning and filtering">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="font-semibold">Ticket checks and relevant evidence</h3><p className="text-xs text-slate-600">Review field corrections and a focused shortlist of historical references.</p></div>
      <button type="button" onClick={onRun} disabled={loading} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{loading ? "Analyzing…" : "Clean & filter"}</button>
    </div>
    {loading && <p role="status" className="mt-3 text-sm text-slate-600">Checking ticket fields and filtering evidence in parallel…</p>}
    {error && <p role="alert" className="mt-3 text-sm text-red-700">Analysis unavailable: {error}. Original ticket and retrieval remain available.</p>}
    {data && <>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
        <span>{data.cache_hit ? "Reused recent analysis" : `Completed in ${(data.elapsed_ms / 1000).toFixed(1)}s`}{data.status === "partial" ? " · Some checks unavailable" : ""}</span>
        <button type="button" onClick={download} className="rounded border border-slate-300 px-3 py-1">Download correction preview</button>
      </div>
      {data.conflicts.map((conflict) => <p key={conflict.field} role="alert" className="mt-3 rounded bg-amber-50 p-3 text-sm text-amber-900">Service interpretations differ: clean {conflict.clean ?? "unresolved"}; filter {conflict.filter ?? "unresolved"}. This field is held for review.</p>)}
      <p className="mt-3 text-sm text-slate-700">{data.clean.reason}</p>
      <div className="mt-3 overflow-x-auto"><table className="w-full text-left text-xs"><thead><tr>{["Field", "Current", "Suggested", "Decision"].map((s) => <th key={s} className="border-b p-2">{s}</th>)}</tr></thead>
        <tbody>{data.clean.fields.map((field) => <tr key={field.field}>
          <td className="border-b p-2 font-medium">{labels[field.field]}</td><td className="border-b p-2">{display(field.current)}</td>
          <td className="border-b p-2">{display(field.suggested)}{field.evidence.length > 0 && <details className="mt-1 text-slate-600"><summary className="cursor-pointer">Current evidence</summary>{field.evidence.map((e) => <p key={e.fact_id} className="mt-1 border-l-2 pl-2">{e.text}</p>)}</details>}</td>
          <td className="border-b p-2">{states[field.state]}</td>
        </tr>)}</tbody></table></div>
      {[...new Set([...data.clean.questions, ...(data.filter?.questions ?? [])])].length > 0 && <div className="mt-3 text-xs"><h4 className="font-semibold">Clarification needed</h4><ul className="ml-4 list-disc">{[...new Set([...data.clean.questions, ...(data.filter?.questions ?? [])])].map((q) => <li key={q}>{q}</li>)}</ul></div>}
      <p className="mt-3 text-xs text-slate-500">Suggestions are provided for review. Downloading creates a copy; the imported ticket remains unchanged.</p>
    </>}
  </section>;
}
