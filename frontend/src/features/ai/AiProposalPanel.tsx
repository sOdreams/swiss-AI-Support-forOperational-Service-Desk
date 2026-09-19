import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Copy,
  FileText,
  Lightbulb,
  Pencil,
  Route,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { confidenceLabel, displayNullable } from "../../lib/utils";
import type { AiProposal } from "../../types/ai";
import type { HumanCorrections, HumanReview } from "../../types/review";
import type { Ticket } from "../../types/ticket";

function CompareRow({
  label,
  current,
  proposed,
  reason,
}: {
  label: string;
  current: string | null | undefined;
  proposed: string | null | undefined;
  reason?: string | null;
}) {
  const same = displayNullable(current) === displayNullable(proposed);
  return (
    <div className="ai-compare-row">
      <p className="ai-eyebrow">{label}</p>
      <div className="ai-compare-values mt-2">
        <div className="ai-current-value">
          <p>Current</p>
          <strong title={displayNullable(current)}>{displayNullable(current)}</strong>
        </div>
        <ChevronRight className="h-4 w-4 text-slate-300" />
        <div className={same ? "ai-suggested-value ai-suggested-value-same" : "ai-suggested-value"}>
          <p>{same ? "Confirmed" : "AI suggests"}</p>
          <strong title={displayNullable(proposed)}>{displayNullable(proposed)}</strong>
        </div>
      </div>
      {reason ? <p className="ai-reason">{reason}</p> : null}
    </div>
  );
}

function decisionLabel(review?: HumanReview) {
  if (!review || review.decision === "pending") return "Pending review";
  if (review.decision === "approved") return "Approved";
  if (review.decision === "edited") return "Edited & approved";
  return "Rejected";
}

function confidenceTone(confidence: number) {
  if (confidence >= 0.85) return "high";
  if (confidence >= 0.65) return "medium";
  return "low";
}

function needsAttention(ticket: Ticket, proposal: AiProposal) {
  const p = String(proposal.proposed_priority ?? ticket.priority ?? "").toLowerCase();
  if (["highest", "p1", "critical"].includes(p)) {
    return {
      title: "Immediate analyst attention",
      body: "The proposed priority indicates a potentially critical operational case. Review the evidence before applying any change.",
      tone: "critical" as const,
    };
  }
  if (proposal.confidence < 0.65 || proposal.pending_questions.length > 0) {
    return {
      title: "Clarification recommended",
      body: "The model does not have enough evidence to make every recommendation confidently. Resolve the missing information first.",
      tone: "warning" as const,
    };
  }
  return null;
}

export function AiProposalPanel({
  ticket,
  proposal,
  review,
  onReviewChange,
}: {
  ticket?: Ticket;
  proposal?: AiProposal;
  review?: HumanReview;
  onReviewChange: (review: HumanReview) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [corrections, setCorrections] = useState<HumanCorrections>({});
  const [comment, setComment] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setEditing(false);
    setCorrections(review?.corrections ?? {});
    setComment(review?.comment ?? "");
    setCopied(false);
  }, [ticket?.issue_id, review]);

  const baseReview = useMemo<HumanReview | undefined>(
    () => ticket ? (review ?? { ticket_id: ticket.issue_id, decision: "pending", corrections: {} }) : undefined,
    [ticket, review],
  );

  if (!ticket) {
    return (
      <aside className="panel-right min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-right">
          <div className="flex items-center gap-2.5">
            <span className="section-step section-step-right">03</span>
            <span className="section-icon section-icon-right"><Sparkles className="h-4 w-4" /></span>
            <div><h2 className="section-title">AI Proposal</h2><p className="section-subtitle">Suggestion only · human review required</p></div>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto overflow-x-hidden p-5">
          <div className="max-w-[280px] text-center">
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#D1FAE5] text-[#147A62]"><Sparkles className="h-5 w-5" /></span>
            <p className="mt-3 text-[14px] font-extrabold text-slate-900">Select a ticket to review the AI proposal</p>
            <p className="mt-1.5 text-[11px] leading-5 text-slate-500">Original Jira data and AI recommendations remain separate.</p>
          </div>
        </div>
      </aside>
    );
  }

  if (!proposal || !baseReview) {
    return (
      <aside className="panel-right min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-right">
          <div className="flex items-center gap-3">
            <span className="section-step section-step-right">03</span>
            <span className="section-icon section-icon-right"><Sparkles className="h-4 w-4" /></span>
            <div><h2 className="section-title">AI Proposal</h2><p className="section-subtitle">Evidence, recommendation and human decision</p></div>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-5">
          <div className="rounded-2xl border border-dashed border-emerald-300 bg-white/80 p-5 text-center shadow-sm">
            <Sparkles className="mx-auto h-6 w-6 text-emerald-600" />
            <p className="mt-3 text-[14px] font-extrabold text-slate-900">Ready for AI analysis</p>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">The ticket is loaded, but no backend proposal exists yet. The frontend deliberately does not invent one.</p>
            <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50/70 px-3 py-2 text-[10px] font-semibold leading-4 text-emerald-800">Expected backend flow: selected ticket → classification → knowledge retrieval → recommendation → human review</div>
          </div>
        </div>
      </aside>
    );
  }

  const save = (decision: HumanReview["decision"], nextCorrections = corrections) => {
    onReviewChange({
      ticket_id: ticket.issue_id,
      decision,
      corrections: nextCorrections,
      reviewer: null,
      reviewed_at: new Date().toISOString(),
      comment: comment || null,
    });
  };

  const attention = needsAttention(ticket, proposal);
  const confidence = Math.max(0, Math.min(100, Math.round(proposal.confidence * 100)));
  const confidenceClass = `confidence-meter confidence-meter-${confidenceTone(proposal.confidence)}`;

  const copyDraft = async () => {
    try {
      await navigator.clipboard.writeText(proposal.draft_response);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <aside className="panel-right min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-right">
        <div className="flex w-full items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="section-step section-step-right">03</span>
            <span className="section-icon section-icon-right"><Sparkles className="h-4 w-4" /></span>
            <div><h2 className="section-title">AI Proposal</h2><p className="section-subtitle">Evidence, recommendation and human decision</p></div>
          </div>
          <span className={`review-state ${baseReview.decision === "pending" ? "review-state-pending" : baseReview.decision === "rejected" ? "review-state-rejected" : "review-state-approved"}`}>{decisionLabel(baseReview)}</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain">
        <div className="w-full min-w-0 space-y-4 p-4 pb-32">
          <section className="ai-hero-card">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="ai-eyebrow text-emerald-700">AI case summary</p>
                <p className="mt-2 text-[13px] leading-5.5 text-slate-700">{proposal.case_summary}</p>
              </div>
              <span className="ai-shield"><ShieldCheck className="h-4 w-4" /></span>
            </div>
            <div className="mt-4 border-t border-emerald-100 pt-3">
              <div className="flex items-center justify-between gap-3 text-[10px] font-bold">
                <span className="text-slate-500">Model confidence</span>
                <span className="text-emerald-800">{confidence}% · {confidenceLabel(proposal.confidence)}</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-emerald-100">
                <div className={confidenceClass} style={{ width: `${confidence}%` }} />
              </div>
            </div>
          </section>

          {attention ? (
            <section className={attention.tone === "critical" ? "ai-attention ai-attention-critical" : "ai-attention ai-attention-warning"}>
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div><h3>{attention.title}</h3><p>{attention.body}</p></div>
            </section>
          ) : null}

          <section className="ai-section-card">
            <div className="mb-3 flex items-center gap-2">
              <Route className="h-4 w-4 text-emerald-700" />
              <div><h3 className="ai-section-title">Current vs AI suggestion</h3><p className="ai-section-copy">Nothing is overwritten until the analyst decides.</p></div>
            </div>
            <CompareRow label="Work type" current={ticket.work_type} proposed={proposal.proposed_work_type} />
            <CompareRow label="Request type" current={ticket.request_type} proposed={proposal.proposed_request_type} />
            <CompareRow label="Priority" current={ticket.priority} proposed={proposal.proposed_priority} reason={proposal.priority_reason} />
            <CompareRow label="Service Team" current={ticket.service_teams.join(", ") || null} proposed={proposal.proposed_service_team} reason={proposal.service_team_reason} />
          </section>

          <section className="ai-section-card">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-emerald-700" />
              <div><h3 className="ai-section-title">Why this recommendation?</h3><p className="ai-section-copy">Concise reasons the analyst can challenge.</p></div>
            </div>
            <div className="mt-3 space-y-2">
              {proposal.priority_reason ? <div className="ai-why-row"><span>Priority</span><p>{proposal.priority_reason}</p></div> : null}
              {proposal.service_team_reason ? <div className="ai-why-row"><span>Routing</span><p>{proposal.service_team_reason}</p></div> : null}
              <div className="ai-why-row"><span>Evidence</span><p>{proposal.sources.length > 0 ? `${proposal.sources.length} supporting source${proposal.sources.length === 1 ? "" : "s"} retrieved.` : "No supporting source retrieved — treat the proposal cautiously."}</p></div>
            </div>
          </section>

          {proposal.pending_questions.length > 0 ? (
            <section className="rounded-2xl border border-amber-200 bg-amber-50/85 p-4">
              <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-700" /><h3 className="text-[12px] font-extrabold text-amber-900">Missing information</h3></div>
              <ul className="mt-2 space-y-1.5 text-[11px] leading-5 text-amber-900/80">{proposal.pending_questions.map((question) => <li key={question}>• {question}</li>)}</ul>
            </section>
          ) : null}

          <section className="ai-section-card">
            <div className="mb-3 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2"><FileText className="h-4 w-4 text-emerald-700" /><h3 className="ai-section-title">Supporting evidence</h3></div>
              <span className="ai-count-badge">{proposal.sources.length}</span>
            </div>
            {proposal.sources.length > 0 ? (
              <div className="space-y-2">
                {proposal.sources.slice(0, 3).map((source) => (
                  <div key={source.id} className="evidence-card">
                    <div className="flex items-center justify-between gap-2"><span className="font-mono text-[10px] font-extrabold text-emerald-700">{source.id}</span><span className="text-[9px] font-semibold uppercase tracking-wide text-slate-400">{source.document_type.replaceAll("_", " ")}</span></div>
                    <p className="mt-1 text-[11px] font-bold text-slate-800">{source.title}</p>
                    {source.excerpt ? <p className="mt-1.5 line-clamp-3 text-[10px] leading-4.5 text-slate-500">{source.excerpt}</p> : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-[10px] leading-4 text-slate-500">No evidence source was retrieved. This is visible on purpose so the analyst can avoid treating unsupported output as fact.</p>
            )}
          </section>

          <section className="ai-section-card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2"><ClipboardCheck className="h-4 w-4 text-emerald-700" /><h3 className="ai-section-title">Draft response</h3></div>
              <button type="button" onClick={() => void copyDraft()} className="copy-draft-button"><Copy className="h-3.5 w-3.5" />{copied ? "Copied" : "Copy"}</button>
            </div>
            <p className="whitespace-pre-wrap rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-[11px] leading-5 text-slate-600">{proposal.draft_response}</p>
          </section>

          {editing ? (
            <section className="rounded-2xl border border-emerald-300 bg-white p-5 shadow-sm">
              <h3 className="text-[13px] font-extrabold text-slate-900">Edit before approval</h3>
              <p className="mt-1 text-[10px] leading-4 text-slate-500">Corrections are stored separately from the original ticket and AI proposal.</p>
              <div className="mt-4 space-y-3">
                {[
                  ["work_type", "Work type", proposal.proposed_work_type],
                  ["request_type", "Request type", proposal.proposed_request_type],
                  ["priority", "Priority", proposal.proposed_priority],
                  ["service_team", "Service team", proposal.proposed_service_team],
                ].map(([key, label, value]) => (
                  <label key={key as string} className="block">
                    <span className="text-[10px] font-bold text-slate-500">{label}</span>
                    <input value={String((corrections as Record<string, unknown>)[key as string] ?? value ?? "")} onChange={(event: { target: { value: string } }) => setCorrections((current) => ({ ...current, [key as string]: event.target.value || null }))} className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-[11px] text-slate-700 outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100" />
                  </label>
                ))}
                <label className="block"><span className="text-[10px] font-bold text-slate-500">Review note</span><textarea value={comment} onChange={(event: { target: { value: string } }) => setComment(event.target.value)} rows={3} className="mt-1.5 w-full resize-none rounded-xl border border-slate-200 px-3 py-2.5 text-[11px] outline-none focus:border-emerald-400 focus:ring-2 focus:ring-emerald-100" /></label>
                <div className="flex gap-2"><button type="button" onClick={() => { save("edited"); setEditing(false); }} className="rounded-xl bg-[#2457E6] px-4 py-2.5 text-[11px] font-bold text-white shadow-sm hover:bg-[#1E49C7]">Save & approve</button><button type="button" onClick={() => setEditing(false)} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-[11px] font-bold text-slate-600 hover:bg-slate-50">Cancel</button></div>
              </div>
            </section>
          ) : null}

          {baseReview.decision !== "pending" ? (
            <section className="feedback-loop-card">
              <CheckCircle2 className="h-5 w-5 shrink-0" />
              <div><h3>Human feedback captured</h3><p>The decision remains a separate review record that can be sent back through the API for evaluation and future model improvement.</p></div>
            </section>
          ) : null}
        </div>
      </div>

      <div className="human-decision-bar">
        <div className="mb-2 flex items-center justify-center gap-1.5 text-center text-[10px] font-semibold text-emerald-800"><ShieldCheck className="h-3.5 w-3.5" />Human-in-the-loop · AI never applies changes automatically</div>
        <div className="grid grid-cols-3 gap-2">
          <button type="button" onClick={() => save("approved", {})} className="decision-button decision-approve"><Check className="h-3.5 w-3.5" />Approve</button>
          <button type="button" onClick={() => setEditing(true)} className="decision-button decision-edit"><Pencil className="h-3.5 w-3.5" />Edit</button>
          <button type="button" onClick={() => save("rejected", {})} className="decision-button decision-reject"><X className="h-3.5 w-3.5" />Reject</button>
        </div>
      </div>
    </aside>
  );
}
