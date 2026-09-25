import {
  AlertTriangle,
  Copy,
  FileText,
  Lightbulb,
  Route,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { confidenceLabel, displayNullable } from "../../lib/utils";
import type { AiProposal } from "../../types/ai";
import type { HumanReview } from "../../types/review";
import type { Ticket } from "../../types/ticket";

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
  const priority = String(proposal.proposed_priority ?? ticket.priority ?? "").toLowerCase();
  if (["highest", "p1", "critical"].includes(priority)) {
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

function SnapshotItem({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="ai-snapshot-item">
      <span>{label}</span>
      <strong>{displayNullable(value)}</strong>
    </div>
  );
}

export function AiProposalPanel({
  ticket,
  proposal,
  review,
}: {
  ticket?: Ticket;
  proposal?: AiProposal;
  review?: HumanReview;
}) {
  const [copied, setCopied] = useState(false);

  if (!ticket) {
    return (
      <aside className="panel-right min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-right">
          <div className="flex items-center gap-2.5">
            <span className="section-step section-step-right">03</span>
            <span className="section-icon section-icon-right"><Sparkles className="h-4 w-4" /></span>
            <div><h2 className="section-title">AI Evidence</h2><p className="section-subtitle">Explanation and supporting sources</p></div>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto overflow-x-hidden p-5">
          <div className="max-w-[280px] text-center">
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#D1FAE5] text-[#147A62]"><Sparkles className="h-5 w-5" /></span>
            <p className="mt-3 text-[14px] font-extrabold text-slate-900">Select a ticket to see the evidence</p>
            <p className="mt-1.5 text-[11px] leading-5 text-slate-500">The recommendation will appear beside the human review workspace.</p>
          </div>
        </div>
      </aside>
    );
  }

  if (!proposal) {
    return (
      <aside className="panel-right min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-right">
          <div className="flex items-center gap-3">
            <span className="section-step section-step-right">03</span>
            <span className="section-icon section-icon-right"><Sparkles className="h-4 w-4" /></span>
            <div><h2 className="section-title">AI Evidence</h2><p className="section-subtitle">Explanation and supporting sources</p></div>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto p-5">
          <div className="rounded-2xl border border-dashed border-emerald-300 bg-white/80 p-5 text-center shadow-sm">
            <Sparkles className="mx-auto h-6 w-6 animate-pulse text-emerald-600" />
            <p className="mt-3 text-[14px] font-extrabold text-slate-900">Analyzing this ticket</p>
            <p className="mt-2 text-[11px] leading-5 text-slate-500">Retrieving historical evidence and preparing the recommendation.</p>
          </div>
        </div>
      </aside>
    );
  }

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
            <div><h2 className="section-title">AI Evidence</h2><p className="section-subtitle">Explanation and supporting sources</p></div>
          </div>
          <span className={`review-state ${review?.decision === "pending" || !review ? "review-state-pending" : review.decision === "rejected" ? "review-state-rejected" : "review-state-approved"}`}>{decisionLabel(review)}</span>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain">
        <div className="w-full min-w-0 space-y-4 p-4 pb-5">
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
              <div><h3 className="ai-section-title">AI routing snapshot</h3><p className="ai-section-copy">The values the reviewer can accept or change in the middle panel.</p></div>
            </div>
            <div className="ai-snapshot-grid">
              <SnapshotItem label="Affected service" value={proposal.affected_services_suggestion.join(", ")} />
              <SnapshotItem label="Service team" value={proposal.proposed_service_team} />
              <SnapshotItem label="Assignee" value={proposal.proposed_assignee} />
              <SnapshotItem label="Priority" value={proposal.proposed_priority} />
              <SnapshotItem label="Urgency" value={proposal.proposed_urgency} />
              <SnapshotItem label="Impact" value={proposal.proposed_impact} />
            </div>
          </section>

          <section className="ai-section-card">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-4 w-4 text-emerald-700" />
              <div><h3 className="ai-section-title">Why this recommendation?</h3><p className="ai-section-copy">Short reasons the analyst can challenge.</p></div>
            </div>
            <div className="mt-3 space-y-2">
              {proposal.priority_reason ? <div className="ai-why-row"><span>Priority</span><p>{proposal.priority_reason}</p></div> : null}
              {proposal.service_team_reason ? <div className="ai-why-row"><span>Routing</span><p>{proposal.service_team_reason}</p></div> : null}
              <div className="ai-why-row"><span>Evidence</span><p>{proposal.sources.length > 0 ? `${proposal.sources.length} supporting source${proposal.sources.length === 1 ? "" : "s"} retrieved.` : "No supporting source retrieved — treat the proposal cautiously."}</p></div>
            </div>
          </section>

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
              <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-[10px] leading-4 text-slate-500">No evidence source was retrieved. Avoid treating unsupported output as fact.</p>
            )}
          </section>

          <section className="ai-section-card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2"><FileText className="h-4 w-4 text-emerald-700" /><h3 className="ai-section-title">Draft response</h3></div>
              <button type="button" onClick={() => void copyDraft()} className="copy-draft-button"><Copy className="h-3.5 w-3.5" />{copied ? "Copied" : "Copy"}</button>
            </div>
            <p className="whitespace-pre-wrap rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-[11px] leading-5 text-slate-600">{proposal.draft_response}</p>
          </section>

          <p className="ai-review-note"><ShieldCheck className="h-3.5 w-3.5" />Make the final decision in the middle review workspace.</p>
        </div>
      </div>
    </aside>
  );
}
