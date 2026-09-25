import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ClipboardCheck,
  Pencil,
  ShieldCheck,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { submitProcessedTicket } from "../../services/api";
import { confidenceLabel, displayNullable } from "../../lib/utils";
import type { AiProposal } from "../../types/ai";
import type { ProcessTicketPayload } from "../../types/processing";
import type { HumanCorrections, HumanReview } from "../../types/review";
import type { Ticket } from "../../types/ticket";

type ReviewFieldKey = "work_type" | "request_type" | "priority" | "service_team";

interface ReviewRow {
  key: ReviewFieldKey;
  label: string;
  current: string | null | undefined;
  proposed: string | null | undefined;
}

function decisionLabel(review?: HumanReview) {
  if (!review || review.decision === "pending") return "Pending review";
  if (review.decision === "approved") return "Approved";
  if (review.decision === "edited") return "Edited & approved";
  return "Rejected";
}

function optionKindLabel(kind: "recommended" | "clarification" | "escalation") {
  if (kind === "recommended") return "Recommended";
  if (kind === "clarification") return "Clarify first";
  return "Safe alternative";
}

function ReviewCompareRow({
  row,
  correction,
}: {
  row: ReviewRow;
  correction?: string | null;
}) {
  const finalValue = correction ?? row.proposed;
  const isEdited = correction !== undefined && correction !== row.proposed;
  const isSame = displayNullable(row.current) === displayNullable(row.proposed);

  return (
    <div className="review-compare-row">
      <div className="review-field-name">
        <span>{row.label}</span>
        {isSame ? <small>Already aligned</small> : <small>Needs review</small>}
      </div>
      <div className="review-value review-value-current">{displayNullable(row.current)}</div>
      <div className={`review-value review-value-proposed ${isSame ? "review-value-confirmed" : ""}`}>
        {displayNullable(row.proposed)}
      </div>
      <div className={`review-value review-value-final ${isEdited ? "review-value-edited" : ""}`}>
        {displayNullable(finalValue)}
      </div>
    </div>
  );
}

export function HumanReviewWorkspace({
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
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [realSolution, setRealSolution] = useState("");
  const [selectedAspect, setSelectedAspect] = useState<string | null>(null);
  const [processing, setProcessing] = useState(false);
  const [processedStatus, setProcessedStatus] = useState<"api" | "local" | null>(null);
  const [processError, setProcessError] = useState<string | null>(null);

  useEffect(() => {
    setEditing(false);
    setCorrections(review?.corrections ?? {});
    setComment(review?.comment ?? "");
    setSelectedOptionId(review?.corrections.resolution_option_id ?? proposal?.resolution_options?.[0]?.id ?? null);
    setRealSolution("");
    setSelectedAspect(null);
    setProcessedStatus(null);
    setProcessError(null);
  }, [ticket?.issue_id, proposal?.ticket_id, proposal?.resolution_options, review]);

  const baseReview = useMemo<HumanReview | undefined>(
    () => ticket ? (review ?? { ticket_id: ticket.issue_id, decision: "pending", corrections: {} }) : undefined,
    [ticket, review],
  );

  if (!ticket) return null;

  const rows: ReviewRow[] = proposal ? [
    { key: "work_type", label: "Work type", current: ticket.work_type, proposed: proposal.proposed_work_type },
    { key: "request_type", label: "Request type", current: ticket.request_type, proposed: proposal.proposed_request_type },
    { key: "priority", label: "Priority", current: ticket.priority, proposed: proposal.proposed_priority },
    { key: "service_team", label: "Service team", current: ticket.service_teams.join(", ") || null, proposed: proposal.proposed_service_team },
  ] : [];
  const resolutionOptions = proposal?.resolution_options ?? [];
  const selectedOption = resolutionOptions.find((option) => option.id === selectedOptionId) ?? null;

  const businessAspects = [
    `Service continuity — availability, reliability, or access to ${ticket.affected_business_or_it_services[0] ?? "the affected service"}.`,
    `Business productivity — users in ${ticket.business_entity ?? "the affected business area"} are blocked, delayed, or working with reduced capability.`,
    ticket.business_critical_for_entity
      ? "Critical business / regulatory impact — disruption may affect time-sensitive, financial, compliance, or executive processes."
      : "Operational / customer impact — downstream delivery, service quality, or customer-facing work may be affected.",
  ];

  const save = (decision: HumanReview["decision"], nextCorrections = corrections) => {
    const reviewCorrections = selectedOptionId ? { ...nextCorrections, resolution_option_id: selectedOptionId } : nextCorrections;
    onReviewChange({
      ticket_id: ticket.issue_id,
      decision,
      corrections: reviewCorrections,
      reviewer: null,
      reviewed_at: new Date().toISOString(),
      comment: comment || null,
    });
  };

  const saveProcessingFeedback = async () => {
    if (!proposal) return;
    if (!selectedAspect) {
      setProcessError("Select the business aspect affected by this ticket.");
      return;
    }
    setProcessing(true);
    setProcessError(null);
    const payload: ProcessTicketPayload = {
      issue_id: ticket.issue_id,
      issue_key: ticket.issue_key,
      recommended_solution: selectedOption?.description ?? proposal.draft_response,
      real_solution: realSolution.trim() || null,
      affected_business_aspect: selectedAspect,
      processed_at: new Date().toISOString(),
      source: "human_resolution_workflow",
    };
    try {
      await submitProcessedTicket(payload);
      setProcessedStatus("api");
    } catch {
      try {
        const key = "swisslife-processed-feedback";
        const stored = JSON.parse(localStorage.getItem(key) ?? "[]") as ProcessTicketPayload[];
        localStorage.setItem(key, JSON.stringify([...stored, payload]));
        setProcessedStatus("local");
      } catch {
        setProcessError("The processing feedback could not be saved.");
      }
    } finally {
      setProcessing(false);
    }
  };

  return (
    <section className="review-workspace-card">
      <div className="review-workspace-heading">
        <div>
          <p className="review-eyebrow">Human review</p>
          <h2>Compare and decide</h2>
          <p>Review the source values, challenge the recommendation, then record the final decision.</p>
        </div>
        <span className={`review-state review-state-${baseReview?.decision === "pending" ? "pending" : baseReview?.decision === "rejected" ? "rejected" : "approved"}`}>
          {decisionLabel(baseReview)}
        </span>
      </div>

      {!proposal ? (
        <div className="review-loading-state">
          <ClipboardCheck className="h-5 w-5 animate-pulse text-[#315F9E]" />
          <div>
            <strong>Preparing the recommendation</strong>
            <span>The original ticket is loaded. The evidence-backed analysis will appear here shortly.</span>
          </div>
        </div>
      ) : (
        <>
          <div className="review-table-wrap">
            <div className="review-table-head">
              <span>Field</span>
              <span>Current</span>
              <span>AI suggestion</span>
              <span>Final decision</span>
            </div>
            {rows.map((row) => (
              <ReviewCompareRow key={row.key} row={row} correction={corrections[row.key] as string | null | undefined} />
            ))}
          </div>

          <div className="review-signal-row">
            <div className="review-signal review-signal-confidence">
              <span>AI confidence</span>
              <strong>{Math.round(proposal.confidence * 100)}% · {confidenceLabel(proposal.confidence)}</strong>
            </div>
            <div className="review-signal review-signal-evidence">
              <span>Evidence</span>
              <strong>{proposal.sources.length} supporting source{proposal.sources.length === 1 ? "" : "s"}</strong>
            </div>
            {proposal.pending_questions.length > 0 ? (
              <div className="review-signal review-signal-warning">
                <AlertTriangle className="h-3.5 w-3.5" />
                <strong>{proposal.pending_questions.length} clarification{proposal.pending_questions.length === 1 ? "" : "s"} needed</strong>
              </div>
            ) : null}
          </div>

          <div className="review-options-card">
            <div className="review-options-heading">
              <div>
                <p className="review-eyebrow">Resolution paths</p>
                <h3>Choose one path for review</h3>
                <p>These are proposals only. Selecting one records your preference; it does not execute a change.</p>
              </div>
              <span className="review-option-count">{resolutionOptions.length} options</span>
            </div>
            {resolutionOptions.length > 0 ? (
              <div className="review-options-list">
                {resolutionOptions.slice(0, 2).map((option) => {
                  const selected = selectedOptionId === option.id;
                  return (
                    <button key={option.id} type="button" aria-pressed={selected} aria-label={`${selected ? "Selected" : "Select"} resolution path: ${option.title}`} onClick={() => setSelectedOptionId(option.id)} className={`review-option-card ${selected ? "review-option-card-selected" : ""}`}>
                      <div className="review-option-topline">
                        <span className={`review-option-badge review-option-badge-${option.kind}`}>{optionKindLabel(option.kind)}</span>
                        {selected ? <CheckCircle2 className="h-4 w-4 text-[#147A62]" /> : null}
                      </div>
                      <strong>{option.title}</strong>
                      <span className="review-option-description">{option.description}</span>
                      {option.prerequisites.length > 0 ? <span className="review-option-detail"><b>Check first:</b> {option.prerequisites.join(" ")}</span> : null}
                      {option.expected_outcome ? <span className="review-option-detail"><b>Expected outcome:</b> {option.expected_outcome}</span> : null}
                      {option.source_ids.length > 0 ? <span className="review-option-sources">{option.source_ids.length} linked evidence source{option.source_ids.length === 1 ? "" : "s"}</span> : <span className="review-option-sources">Safety path · no direct fix assumed</span>}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="review-options-empty">No separate resolution paths were returned. Review the draft response and record the actual outcome manually.</div>
            )}
          </div>

          {editing ? (
            <div className="review-edit-card">
              <div>
                <h3>Make a correction before approval</h3>
                <p>Corrections stay separate from the original Jira record and AI suggestion.</p>
              </div>
              <div className="review-edit-grid">
                {[
                  ["work_type", "Work type", proposal.proposed_work_type],
                  ["request_type", "Request type", proposal.proposed_request_type],
                  ["priority", "Priority", proposal.proposed_priority],
                  ["service_team", "Service team", proposal.proposed_service_team],
                ].map(([key, label, value]) => (
                  <label key={key as string}>
                    <span>{label}</span>
                    <input
                      value={String((corrections as Record<string, unknown>)[key as string] ?? value ?? "")}
                      onChange={(event) => setCorrections((current) => ({ ...current, [key as string]: event.target.value || null }))}
                    />
                  </label>
                ))}
              </div>
              <label className="review-note-field">
                <span>Review note</span>
                <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={2} placeholder="Why was the suggestion changed?" />
              </label>
              <div className="review-edit-actions">
                <button type="button" className="review-primary-button" onClick={() => { save("edited"); setEditing(false); }}><Check className="h-3.5 w-3.5" />Save & approve</button>
                <button type="button" className="review-secondary-button" onClick={() => setEditing(false)}>Cancel</button>
              </div>
            </div>
          ) : null}

          <div className="review-decision-bar">
            <div>
              <div className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-[#147A62]" /><strong>Human decision required</strong></div>
              <span>{selectedOption ? `Selected path: ${selectedOption.title}` : "Choose a resolution path; AI suggestions never overwrite the source ticket automatically."}</span>
            </div>
            <div className="review-decision-actions">
              <button type="button" className="review-primary-button" onClick={() => save("approved")}><Check className="h-3.5 w-3.5" />Approve</button>
              <button type="button" className="review-secondary-button" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Edit</button>
              <button type="button" className="review-danger-button" onClick={() => save("rejected")}><X className="h-3.5 w-3.5" />Reject</button>
            </div>
          </div>

          <div className="review-outcome-card">
            <div>
              <p className="review-eyebrow">After the decision</p>
              <h3>Record the real outcome</h3>
              <p>Capture what the analyst actually did so reviewed outcomes can be evaluated later.</p>
            </div>
            <label>
              <span>Real solution <em>(optional)</em></span>
              <textarea value={realSolution} onChange={(event) => { setRealSolution(event.target.value); setProcessError(null); }} rows={3} placeholder="What did the analyst actually do?" />
            </label>
            <div>
              <span className="review-outcome-label">Affected business aspect</span>
              <div className="review-aspect-list">
                {businessAspects.map((aspect, index) => (
                  <button key={aspect} type="button" onClick={() => { setSelectedAspect(aspect); setProcessError(null); }} className={selectedAspect === aspect ? "review-aspect review-aspect-selected" : "review-aspect"}>
                    <span>{index + 1}</span>{aspect}
                  </button>
                ))}
              </div>
            </div>
            {processError ? <p className="review-process-error">{processError}</p> : null}
            {processedStatus ? <p className="review-process-success"><CheckCircle2 className="h-3.5 w-3.5" />Feedback saved {processedStatus === "api" ? "to the triage service" : "locally for later sync"}.</p> : null}
            <button type="button" onClick={() => void saveProcessingFeedback()} disabled={processing || !selectedAspect} className="review-save-outcome" >
              <ClipboardCheck className="h-3.5 w-3.5" />{processing ? "Saving…" : "Save processing feedback"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
