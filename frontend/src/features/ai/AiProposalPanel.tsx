import { Check, ChevronRight, FileText, Pencil, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NullableValue } from "../../components/NullableValue";
import { PriorityBadge } from "../../components/PriorityBadge";
import { confidenceLabel } from "../../lib/utils";
import type { AiProposal } from "../../types/ai";
import type { HumanCorrections, HumanReview } from "../../types/review";
import type { Ticket } from "../../types/ticket";

function CompareRow({ label, current, proposed, reason }: { label: string; current: string | null; proposed: string | null; reason?: string | null }) {
  const changed = current !== proposed && proposed !== null;
  return (
    <div className="border-b border-slate-100 py-2.5 last:border-b-0">
      <p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-slate-400">{label}</p>
      <div className="mt-1 flex items-center gap-2 text-[11px]">
        <span className="min-w-0 flex-1 truncate text-slate-600"><NullableValue value={current} /></span>
        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-slate-300" />
        <span className={`min-w-0 flex-1 truncate font-semibold ${changed ? "text-blue-700" : "text-slate-700"}`}><NullableValue value={proposed} emptyLabel="No proposal" /></span>
      </div>
      {reason ? <p className="mt-1.5 text-[9px] leading-4 text-slate-500">{reason}</p> : null}
    </div>
  );
}

function decisionLabel(review: HumanReview) {
  if (review.decision === "approved") return "Approved by analyst";
  if (review.decision === "edited") return "Edited by analyst";
  if (review.decision === "rejected") return "Rejected by analyst";
  return "Pending human review";
}

export function AiProposalPanel({ ticket, proposal, review, onReviewChange }: { ticket?: Ticket; proposal?: AiProposal; review?: HumanReview; onReviewChange: (review: HumanReview) => void }) {
  const [tab, setTab] = useState<"proposal" | "sources" | "draft">("proposal");
  const [editing, setEditing] = useState(false);
  const [corrections, setCorrections] = useState<HumanCorrections>({});
  const [comment, setComment] = useState("");

  useEffect(() => { setTab("proposal"); setEditing(false); setCorrections(review?.corrections ?? {}); setComment(review?.comment ?? ""); }, [ticket?.issue_id, review]);

  const baseReview = useMemo<HumanReview | undefined>(() => ticket ? (review ?? { ticket_id: ticket.issue_id, decision: "pending", corrections: {} }) : undefined, [ticket, review]);
  if (!ticket || !proposal || !baseReview) return <aside className="flex w-[380px] items-center justify-center border-l border-[#DCE3EC] bg-[#F4F7FD] p-6 text-center text-xs text-slate-400">Select a ticket to view the AI proposal.</aside>;

  const save = (decision: HumanReview["decision"], nextCorrections = corrections) => onReviewChange({ ticket_id: ticket.issue_id, decision, corrections: nextCorrections, reviewer: "Razon", reviewed_at: new Date().toISOString(), comment: comment || null });

  return (
    <aside className="flex min-h-0 w-[380px] shrink-0 flex-col border-l border-[#DCE3EC] bg-[#F4F7FD]">
      <div className="border-b border-[#DCE3EC] bg-[#EEF3FB] px-4 py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div><div className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-blue-700" /><h2 className="text-xs font-bold text-slate-900">AI Proposal</h2></div><p className="mt-1 text-[10px] text-slate-500">Compare with the original Jira data before deciding.</p></div>
          <span className={`rounded border px-2 py-1 text-[9px] font-semibold ${baseReview.decision === "pending" ? "border-slate-200 bg-white text-slate-500" : baseReview.decision === "rejected" ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{decisionLabel(baseReview)}</span>
        </div>
        <div className="mt-3 grid grid-cols-3 rounded-md border border-[#DCE3EC] bg-white/70 p-1">
          {(["proposal", "sources", "draft"] as const).map((value) => <button key={value} type="button" onClick={() => setTab(value)} className={`rounded px-2 py-1.5 text-[9px] font-semibold capitalize ${tab === value ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"}`}>{value}</button>)}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3.5">
        {tab === "proposal" ? <div className="space-y-3">
          <section className="rounded-lg border border-[#DCE3EC] bg-white p-3.5">
            <div className="flex items-start justify-between gap-3"><div><p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-blue-700">AI case summary</p><p className="mt-2 text-[11px] leading-5 text-slate-700">{proposal.case_summary}</p></div><span className="shrink-0 rounded border border-blue-200 bg-blue-50 px-2 py-1 text-[9px] font-semibold text-blue-700">{confidenceLabel(proposal.confidence)} confidence</span></div>
          </section>

          <section className="rounded-lg border border-[#DCE3EC] bg-white p-3.5">
            <div className="mb-2 flex items-center justify-between"><div><p className="text-[10px] font-bold text-slate-800">Current vs AI proposal</p><p className="mt-0.5 text-[9px] text-slate-400">Left = recorded Jira value · Right = AI suggestion</p></div></div>
            <CompareRow label="Work type" current={ticket.work_type} proposed={proposal.proposed_work_type} />
            <CompareRow label="Request type" current={ticket.request_type} proposed={proposal.proposed_request_type} />
            <div className="border-b border-slate-100 py-2.5"><p className="text-[9px] font-semibold uppercase tracking-[0.07em] text-slate-400">Priority</p><div className="mt-1 flex items-center gap-2"><PriorityBadge priority={ticket.priority} /><ChevronRight className="h-3.5 w-3.5 text-slate-300" /><PriorityBadge priority={proposal.proposed_priority} /></div>{proposal.priority_reason ? <p className="mt-1.5 text-[9px] leading-4 text-slate-500">{proposal.priority_reason}</p> : null}</div>
            <CompareRow label="Service team" current={ticket.service_teams.join(", ") || null} proposed={proposal.proposed_service_team} reason={proposal.service_team_reason} />
          </section>

          <details className="rounded-lg border border-[#DCE3EC] bg-white">
            <summary className="cursor-pointer px-3.5 py-3 text-[10px] font-semibold text-blue-700">Review additional proposed fields</summary>
            <div className="border-t border-slate-100 px-3.5 pb-2"><CompareRow label="Urgency" current={ticket.urgency} proposed={proposal.proposed_urgency} reason={proposal.urgency_reason} /><CompareRow label="Impact" current={ticket.impact} proposed={proposal.proposed_impact} reason={proposal.impact_reason} /><CompareRow label="Severity" current={ticket.severity} proposed={proposal.proposed_severity} reason={proposal.severity_reason} /></div>
          </details>

          {proposal.pending_questions.length > 0 ? <section className="rounded-lg border border-blue-200 bg-blue-50 p-3"><p className="text-[10px] font-bold text-slate-800">Questions pending</p><ul className="mt-2 space-y-1 text-[10px] leading-4 text-slate-600">{proposal.pending_questions.map((q) => <li key={q}>• {q}</li>)}</ul></section> : null}

          <section className="rounded-lg border border-[#DCE3EC] bg-white p-3.5">
            <p className="text-[10px] font-bold text-slate-800">Human review</p>
            <p className="mt-1 text-[9px] leading-4 text-slate-400">Approve, correct or reject the AI proposal. Original Jira values remain separate until the API saves an approved decision.</p>
            {editing ? <div className="mt-3 space-y-2">
              {[
                ["work_type", "Work type", proposal.proposed_work_type],
                ["request_type", "Request type", proposal.proposed_request_type],
                ["priority", "Priority", proposal.proposed_priority],
                ["service_team", "Service team", proposal.proposed_service_team],
                ["urgency", "Urgency", proposal.proposed_urgency],
                ["impact", "Impact", proposal.proposed_impact],
              ].map(([key, label, value]) => <label key={key as string} className="block"><span className="text-[9px] font-medium text-slate-500">{label}</span><input value={String((corrections as Record<string, unknown>)[key as string] ?? value ?? "")} onChange={(e: { target: { value: string } }) => setCorrections((current) => ({ ...current, [key as string]: e.target.value || null }))} className="mt-1 w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[10px] text-slate-700 outline-none focus:border-blue-300" /></label>)}
              <label className="block"><span className="text-[9px] font-medium text-slate-500">Reviewer comment</span><textarea value={comment} onChange={(e: { target: { value: string } }) => setComment(e.target.value)} rows={2} className="mt-1 w-full resize-none rounded-md border border-slate-200 px-2 py-1.5 text-[10px] outline-none focus:border-blue-300" /></label>
              <div className="flex gap-2"><button type="button" onClick={() => { save("edited"); setEditing(false); }} className="rounded-md bg-blue-700 px-3 py-1.5 text-[9px] font-semibold text-white">Save edits</button><button type="button" onClick={() => setEditing(false)} className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-[9px] font-semibold text-slate-600">Cancel</button></div>
            </div> : <div className="mt-3 grid grid-cols-3 gap-2"><button type="button" onClick={() => save("approved", {})} className="inline-flex items-center justify-center gap-1 rounded-md bg-blue-700 px-2 py-2 text-[9px] font-semibold text-white"><Check className="h-3 w-3" />Approve</button><button type="button" onClick={() => setEditing(true)} className="inline-flex items-center justify-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-2 text-[9px] font-semibold text-slate-700"><Pencil className="h-3 w-3" />Edit</button><button type="button" onClick={() => save("rejected", {})} className="inline-flex items-center justify-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-2 text-[9px] font-semibold text-red-700"><X className="h-3 w-3" />Reject</button></div>}
          </section>
        </div> : null}

        {tab === "sources" ? <div className="space-y-3"><section className="rounded-lg border border-[#DCE3EC] bg-white p-3.5"><div className="flex items-center gap-2"><FileText className="h-4 w-4 text-blue-700" /><h3 className="text-[10px] font-bold text-slate-800">Sources used</h3></div>{proposal.sources.length ? <div className="mt-3 space-y-2">{proposal.sources.map((source) => <div key={source.id} className="rounded-md border border-slate-100 bg-slate-50 p-3"><div className="flex items-start justify-between gap-2"><div><p className="font-mono text-[9px] font-bold text-blue-700">{source.id}</p><p className="mt-1 text-[10px] font-semibold text-slate-800">{source.title}</p><p className="mt-1 text-[9px] text-slate-400">{source.document_type}{source.section ? ` · ${source.section}` : ""}</p></div>{source.relevance_score ? <span className="text-[9px] text-slate-400">{Math.round(source.relevance_score * 100)}% relevance</span> : null}</div>{source.excerpt ? <p className="mt-2 text-[9px] leading-4 text-slate-500">{source.excerpt}</p> : null}</div>)}</div> : <p className="mt-3 text-[10px] italic text-slate-400">No supporting source was found. The AI should not invent a resolution.</p>}</section></div> : null}

        {tab === "draft" ? <section className="rounded-lg border border-[#DCE3EC] bg-white p-3.5"><p className="text-[10px] font-bold text-slate-800">Draft response</p><p className="mt-1 text-[9px] text-slate-400">AI-generated · review before sending</p><textarea readOnly value={proposal.draft_response} rows={12} className="mt-3 w-full resize-none rounded-md border border-slate-200 bg-slate-50 p-3 text-[10px] leading-5 text-slate-700" /></section> : null}
      </div>
    </aside>
  );
}
