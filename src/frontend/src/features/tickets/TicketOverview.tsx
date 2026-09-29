import {
  ArrowLeft,
  BrainCircuit,
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Columns3,
  Database,
  FileText,
  LayoutGrid,
  LoaderCircle,
  RefreshCw,
  Send,
  Sparkles,
  TriangleAlert,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { submitRagFeedback } from "../../services/api";
import type {
  AiSolutionFeedback,
  ProcessedTicketRecord,
  ProcessTicketPayload,
  RelevanceRating,
} from "../../types/processing";
import type { Ticket } from "../../types/ticket";
import type {
  Prediction,
  TicketAnalysisStatus,
  TriageResult,
} from "../../types/triage";

const TICKETS_PER_GROUP = 6;
const GROUPS_PER_CATEGORY = 8;

type CategoryGroup = { label: string; count: number; tickets: Ticket[] };
type CategoryCard = {
  title: string;
  subtitle: string;
  groups: CategoryGroup[];
};

const RELEVANCE_OPTIONS: Array<{
  value: RelevanceRating;
  label: string;
  helper: string;
}> = [
  {
    value: "highly_relevant",
    label: "Highly relevant",
    helper: "Correct or almost directly usable",
  },
  {
    value: "medium_relevant",
    label: "Medium relevant",
    helper: "Useful, but incomplete or needs edits",
  },
  {
    value: "poor_relevant",
    label: "Poor relevant",
    helper: "Not useful for resolving this case",
  },
];

function normalizeLabel(value: string | null | undefined) {
  return value?.trim() || "Not predicted";
}

function priorityRank(priority: string | null | undefined) {
  const value = (priority ?? "").toLowerCase();
  if (value === "highest" || value === "p1") return 0;
  if (value === "high" || value === "p2") return 1;
  if (value === "medium" || value === "p3") return 2;
  if (value === "low" || value === "p4") return 3;
  if (value === "lowest" || value === "p5") return 4;
  return 5;
}

function buildGroups(
  tickets: Ticket[],
  getValues: (ticket: Ticket) => Array<string | null | undefined>,
): CategoryGroup[] {
  const groups = new Map<string, Ticket[]>();
  for (const ticket of tickets) {
    const values = getValues(ticket);
    const normalized = values.length
      ? values.map(normalizeLabel)
      : ["Not predicted"];
    for (const label of [...new Set(normalized)]) {
      const current = groups.get(label) ?? [];
      current.push(ticket);
      groups.set(label, current);
    }
  }

  return [...groups.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .slice(0, GROUPS_PER_CATEGORY)
    .map(([label, groupTickets]) => ({
      label,
      count: groupTickets.length,
      tickets: groupTickets.slice(0, TICKETS_PER_GROUP),
    }));
}

function confidenceLabel(value?: number | null) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : null;
}

function PredictionRow({
  label,
  prediction,
  priority = false,
}: {
  label: string;
  prediction?: Prediction;
  priority?: boolean;
}) {
  const confidence = confidenceLabel(prediction?.confidence);
  return (
    <div className="rounded-xl border border-blue-100 bg-white px-3 py-2.5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="block text-[9px] font-black uppercase tracking-[0.08em] text-blue-500">
            {label}
          </span>
          <div className="mt-1 min-w-0 text-[12px] font-extrabold text-slate-800">
            {priority && prediction?.value ? (
              <PriorityBadge priority={prediction.value} />
            ) : (
              <span className="break-words">
                {prediction?.value ?? "Not predicted"}
              </span>
            )}
          </div>
        </div>
        {confidence ? (
          <span className="shrink-0 rounded-full bg-blue-50 px-2 py-1 text-[9px] font-black text-blue-700">
            {confidence}
          </span>
        ) : null}
      </div>
      {prediction?.reason ? (
        <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
          {prediction.reason}
        </p>
      ) : null}
    </div>
  );
}

function TicketChip({
  ticket,
  analysis,
  onClick,
}: {
  ticket: Ticket;
  analysis: TriageResult;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="category-ticket-button"
      title={ticket.summary}
    >
      <Sparkles className="h-3.5 w-3.5 shrink-0 text-blue-500" />
      <span className="min-w-0 flex-1 truncate">{ticket.summary}</span>
      {analysis.analysis.priority.value ? (
        <span className="shrink-0 text-[9px] font-black text-slate-400">
          {analysis.analysis.priority.value}
        </span>
      ) : null}
      <ChevronRight className="h-3.5 w-3.5 shrink-0" />
    </button>
  );
}

function RelevanceSelector({
  solutionId,
  value,
  onChange,
}: {
  solutionId: string;
  value: RelevanceRating | null;
  onChange: (rating: RelevanceRating) => void;
}) {
  return (
    <div
      className="relevance-rating-group"
      role="radiogroup"
      aria-label={`Relevance rating for ${solutionId}`}
    >
      {RELEVANCE_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`relevance-rating-button relevance-${option.value} ${value === option.value ? "relevance-rating-button-selected" : ""}`}
          aria-pressed={value === option.value}
          title={option.helper}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function AnalysisUnavailable({
  status,
  onRetry,
}: {
  status: TicketAnalysisStatus;
  onRetry: () => void;
}) {
  if (status === "analyzing" || status === "queued") {
    return (
      <div className="rounded-2xl border border-blue-200 bg-blue-50/60 px-5 py-8 text-center">
        <LoaderCircle className="mx-auto h-6 w-6 animate-spin text-blue-600" />
        <p className="mt-3 text-[13px] font-extrabold text-slate-800">
          AI is analyzing this ticket
        </p>
        <p className="mt-1 text-[11px] text-slate-500">
          The original ticket remains visible while the backend calculates
          routing, priority, solutions and affected areas.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50/70 px-5 py-6 text-center">
      <TriangleAlert className="mx-auto h-6 w-6 text-amber-600" />
      <p className="mt-3 text-[13px] font-extrabold text-slate-800">
        AI analysis is not available
      </p>
      <p className="mt-1 text-[11px] text-slate-500">
        Check the backend connection and retry. No original
        Priority/Urgency/Impact is used as the AI answer.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-3 inline-flex items-center gap-2 rounded-xl bg-amber-600 px-3 py-2 text-[11px] font-bold text-white hover:bg-amber-700"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Retry analysis
      </button>
    </div>
  );
}

function TicketProcessor({
  ticket,
  analysis,
  analysisStatus,
  onBack,
  onRetryAnalysis,
  onProcessed,
}: {
  ticket: Ticket;
  analysis?: TriageResult;
  analysisStatus: TicketAnalysisStatus;
  onBack: () => void;
  onRetryAnalysis: () => void;
  onProcessed: (ticket: Ticket, record: ProcessedTicketRecord) => void;
}) {
  const solutions = analysis?.recommended_solutions ?? [];
  const areas = analysis?.affected_areas ?? [];
  const [selectedSolutionId, setSelectedSolutionId] = useState<string | null>(
    null,
  );
  const [ratings, setRatings] = useState<
    Record<string, RelevanceRating | null>
  >({});
  const [realSolution, setRealSolution] = useState("");
  const [selectedAreaId, setSelectedAreaId] = useState<string | null>(null);
  const [customArea, setCustomArea] = useState(""); // NUEVO: Estado para área manual
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelectedSolutionId(null);
    setRatings({});
    setRealSolution("");
    setSelectedAreaId(null);
    setCustomArea("");
    setError(null);
  }, [ticket.issue_id, analysis?.ticket_id]);

  const selectedSolution =
    solutions.find((solution) => solution.id === selectedSolutionId) ?? null;
  const selectedArea = areas.find((area) => area.id === selectedAreaId) ?? null;
  const hasResolution = Boolean(selectedSolution || realSolution.trim());
  const hasAreaDecision =
    areas.length === 0 || Boolean(selectedArea) || Boolean(customArea.trim());

  // MODIFICADO: Ya no requiere que allSolutionsRated sea true
  const isComplete =
    analysisStatus === "success" && hasResolution && hasAreaDecision;
  const ratedCount = solutions.filter((solution) =>
    Boolean(ratings[solution.id]),
  ).length;

  const handleSend = async () => {
    if (!analysis) return;
    // Eliminada la validación que forzaba a rellenar los ratings
    if (!hasResolution)
      return setError(
        "Choose one AI solution or write the real solution before sending.",
      );
    if (!hasAreaDecision)
      return setError(
        "Select or enter the affected business area before sending.",
      );

    setSending(true);
    setError(null);
    const processedAt = new Date().toISOString();

    const solutionFeedback: AiSolutionFeedback[] = solutions.map(
      (solution) => ({
        solution_id: solution.id,
        text: solution.description,
        relevance: ratings[solution.id] as RelevanceRating,
        selected: selectedSolutionId === solution.id,
      }),
    );

    const finalAffectedAreaLabel =
      customArea.trim() ||
      selectedArea?.label ||
      "No AI affected-area recommendation";
    const finalAffectedAreaId = customArea.trim()
      ? null
      : (selectedArea?.id ?? null);

    const payload: ProcessTicketPayload = {
      issue_id: ticket.issue_id,
      issue_key: ticket.issue_key,
      selected_solution_id: selectedSolution?.id ?? null,
      selected_solution: selectedSolution?.description ?? null,
      real_solution: realSolution.trim() || null,
      affected_business_aspect: finalAffectedAreaLabel,
      selected_affected_area_id: finalAffectedAreaId,
      original_ticket: ticket.raw,
      ai_analysis: analysis.analysis as unknown as Record<string, unknown>,
      solution_feedback: solutionFeedback,
      rag_context: {
        work_type: analysis.analysis.work_type.value ?? ticket.work_type,
        request_type: ticket.request_type,
        priority: analysis.analysis.priority.value ?? null,
        status: ticket.status,
        business_entity: ticket.business_entity,
        service_teams: analysis.analysis.service_team.value
          ? [analysis.analysis.service_team.value]
          : [],
        affected_services: analysis.analysis.affected_service.value
          ? [analysis.analysis.affected_service.value]
          : [],
      },
      knowledge_candidate: Boolean(realSolution.trim()),
      processed_at: processedAt,
      source: "human_in_the_loop_rag_feedback",
    };

    let syncStatus: ProcessedTicketRecord["sync_status"] = "api";
    try {
      await submitRagFeedback(payload);
    } catch {
      try {
        const key = "service-desk-copilot-rag-feedback";
        const stored = JSON.parse(
          localStorage.getItem(key) ?? "[]",
        ) as ProcessTicketPayload[];
        localStorage.setItem(key, JSON.stringify([...stored, payload]));
        syncStatus = "local";
      } catch {
        setSending(false);
        setError("The feedback could not be saved. Please try again.");
        return;
      }
    }

    onProcessed(ticket, {
      issue_id: ticket.issue_id,
      issue_key: ticket.issue_key,
      summary: ticket.summary,
      selected_solution: selectedSolution?.description ?? null,
      real_solution: realSolution.trim() || null,
      affected_business_aspect: finalAffectedAreaLabel,
      selected_affected_area_id: finalAffectedAreaId,
      original_ticket: ticket.raw,
      ai_analysis: analysis.analysis as unknown as Record<string, unknown>,
      solution_feedback: solutionFeedback,
      knowledge_candidate: Boolean(realSolution.trim()),
      processed_at: processedAt,
      sync_status: syncStatus,
    });
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-4">
      <button type="button" onClick={onBack} className="processor-back-button">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to AI-organized tickets
      </button>

      <section className="processor-ticket-hero">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2 py-1 text-[9.5px] font-black uppercase tracking-[0.07em] text-slate-600">
                Original ticket
              </span>
              <StatusBadge status={ticket.status} />
            </div>
            <h2 className="mt-2 text-[17px] font-black leading-6 text-slate-900">
              {ticket.summary}
            </h2>
          </div>
        </div>
        <p className="mt-3 text-[11px] leading-5 text-slate-600">
          {ticket.description || "No description recorded."}
        </p>

        <div className="processor-info-grid">
          <div>
            <span>Work type</span>
            <strong>{ticket.work_type ?? "Not recorded"}</strong>
          </div>
          <div>
            <span>Request type</span>
            <strong>{ticket.request_type ?? "Not recorded"}</strong>
          </div>
          <div>
            <span>Reported service</span>
            <strong>
              {ticket.affected_business_or_it_services.join(", ") ||
                "Not recorded"}
            </strong>
          </div>
          <div>
            <span>Business entity</span>
            <strong>{ticket.business_entity ?? "Not recorded"}</strong>
          </div>
          <div>
            <span>Reporter</span>
            <strong>{ticket.reporter?.display_name ?? "Not recorded"}</strong>
          </div>
          <div>
            <span>Created</span>
            <strong>{ticket.created_date || "Not recorded"}</strong>
          </div>
          {ticket.service_teams.length ? (
            <div>
              <span>Reported service team</span>
              <strong>{ticket.service_teams.join(", ")}</strong>
            </div>
          ) : null}
          {ticket.assignee ? (
            <div>
              <span>Reported assignee</span>
              <strong>{ticket.assignee.display_name}</strong>
            </div>
          ) : null}
        </div>

        {ticket.all_comments.length ? (
          <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3">
            <div className="mb-2 flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.06em] text-slate-500">
              <FileText className="h-3.5 w-3.5" />
              Original comments
            </div>
            <div className="space-y-2">
              {ticket.all_comments.map((comment) => (
                <p
                  key={comment.id}
                  className="text-[10.5px] leading-4 text-slate-600"
                >
                  <strong>{comment.author.display_name}:</strong> {comment.body}
                </p>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      {analysisStatus !== "success" || !analysis ? (
        <div className="mt-4">
          <AnalysisUnavailable
            status={analysisStatus}
            onRetry={onRetryAnalysis}
          />
        </div>
      ) : (
        <>
          <section className="processor-section">
            <div className="processor-section-heading">
              <span className="processor-section-icon">
                <BrainCircuit className="h-4 w-4" />
              </span>
              <div>
                <h3>AI Analysis</h3>
                <p>
                  These values were added or corrected by the AI system.
                  Original benchmark fields are not used as the displayed
                  answer.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
              <PredictionRow
                label="Work type"
                prediction={analysis.analysis.work_type}
              />
              <PredictionRow
                label="Affected service"
                prediction={analysis.analysis.affected_service}
              />
              <PredictionRow
                label="Service team"
                prediction={analysis.analysis.service_team}
              />
              <PredictionRow
                label="Assignee"
                prediction={analysis.analysis.assignee}
              />
              <PredictionRow
                label="Urgency"
                prediction={analysis.analysis.urgency}
              />
              <PredictionRow
                label="Impact"
                prediction={analysis.analysis.impact}
              />
              <PredictionRow
                label="AI Priority"
                prediction={analysis.analysis.priority}
                priority
              />
              <PredictionRow
                label="Resolution status"
                prediction={analysis.analysis.resolution_status}
              />
            </div>
          </section>

          <section className="rag-feedback-banner">
            <div className="rag-feedback-icon">
              <Database className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h3>Human-in-the-loop review</h3>
              <p>
                The analyst validates AI recommendations instead of blindly
                accepting them. Ratings can later improve retrieval, reranking
                and the knowledge base.
              </p>
            </div>
            <div className="rag-rating-progress">
              <BrainCircuit className="h-3.5 w-3.5" />
              {ratedCount}/{solutions.length} rated
            </div>
          </section>

          <section className="processor-section">
            <div className="processor-section-heading">
              <span className="processor-section-icon">
                <Wrench className="h-4 w-4" />
              </span>
              <div>
                <h3>1. Recommended Solutions</h3>
                <p>
                  Rate each AI recommendation. Use one, or reject them and enter
                  the real solution.
                </p>
              </div>
            </div>

            {solutions.length ? (
              <div className="recommendation-scroll recommendation-scroll-feedback">
                {solutions.map((solution, index) => {
                  const selected = selectedSolutionId === solution.id;
                  const rating = ratings[solution.id] ?? null;
                  return (
                    <article
                      key={solution.id}
                      className={`recommendation-feedback-card ${selected ? "recommendation-feedback-card-selected" : ""}`}
                    >
                      <div className="recommendation-feedback-main">
                        <span className="recommendation-number">
                          {index + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          {solution.title ? (
                            <h4 className="mb-1 text-[11px] font-black text-slate-800">
                              {solution.title}
                            </h4>
                          ) : null}
                          <p className="recommendation-feedback-text">
                            {solution.description}
                          </p>
                          {confidenceLabel(solution.confidence) ? (
                            <p className="mt-1 text-[9.5px] font-bold text-blue-600">
                              AI confidence{" "}
                              {confidenceLabel(solution.confidence)}
                            </p>
                          ) : null}
                          <p className="recommendation-feedback-label">
                            How relevant is this recommendation? (Optional)
                          </p>
                          <RelevanceSelector
                            solutionId={solution.id}
                            value={rating}
                            onChange={(next) => {
                              setRatings((current) => ({
                                ...current,
                                [solution.id]: next,
                              }));
                              setError(null);
                            }}
                          />
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedSolutionId((current) =>
                            current === solution.id ? null : solution.id,
                          );
                          setRealSolution("");
                          setError(null);
                        }}
                        className={`use-solution-button ${selected ? "use-solution-button-selected" : ""}`}
                      >
                        {selected ? (
                          <>
                            <Check className="h-3.5 w-3.5" />
                            Selected solution
                          </>
                        ) : (
                          "Use this solution"
                        )}
                      </button>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-[11px] text-slate-500">
                The backend returned no recommended solutions. The analyst can
                still enter the real solution below.
              </div>
            )}

            <div className="real-solution-wrap real-solution-rag-wrap">
              <label htmlFor="real-solution">
                Real Solution{" "}
                <span>
                  {selectedSolution
                    ? "optional — an AI recommendation is selected"
                    : "use this when AI recommendations are not correct"}
                </span>
              </label>
              <textarea
                id="real-solution"
                value={realSolution}
                onChange={(event) => {
                  setRealSolution(event.target.value);
                  if (event.target.value.trim()) setSelectedSolutionId(null);
                  setError(null);
                }}
                rows={4}
                placeholder="Write the actual solution applied by the analyst. This becomes validated feedback and can be curated as a future knowledge candidate."
              />
              {realSolution.trim() ? (
                <div className="knowledge-candidate-note">
                  <Database className="h-3.5 w-3.5" />
                  Knowledge candidate for validation before vector DB ingestion.
                </div>
              ) : null}
            </div>
          </section>

          <section className="processor-section">
            <div className="processor-section-heading">
              <span className="processor-section-icon processor-section-icon-business">
                <Building2 className="h-4 w-4" />
              </span>
              <div>
                <h3>2. AI Suggested Affected Areas</h3>
                <p>
                  Select the area that best represents the real business impact.
                </p>
              </div>
            </div>
            {areas.length ? (
              <div className="business-aspect-grid mb-3">
                {areas.map((area, index) => {
                  const selected = selectedAreaId === area.id && !customArea;
                  return (
                    <button
                      key={area.id}
                      type="button"
                      onClick={() => {
                        setSelectedAreaId(area.id);
                        setCustomArea("");
                        setError(null);
                      }}
                      className={`business-aspect-option ${selected ? "business-aspect-option-selected" : ""}`}
                    >
                      <span className="business-aspect-number">
                        {index + 1}
                      </span>
                      <span className="min-w-0">
                        <strong className="block">{area.label}</strong>
                        {area.reason ? (
                          <small className="mt-0.5 block text-[9.5px] font-medium opacity-70">
                            {area.reason}
                          </small>
                        ) : null}
                      </span>
                      {confidenceLabel(area.confidence) ? (
                        <span className="ml-auto shrink-0 text-[9px] font-black opacity-60">
                          {confidenceLabel(area.confidence)}
                        </span>
                      ) : null}
                      {selected ? <Check className="h-4 w-4 shrink-0" /> : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-[11px] text-slate-500">
                No affected-area recommendation was returned by the backend.
              </div>
            )}

            <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
              <label
                htmlFor="custom-area"
                className="mb-1 block text-[11px] font-bold text-slate-700"
              >
                Or enter a custom affected area manually:
              </label>
              <input
                id="custom-area"
                type="text"
                className="w-full rounded-lg border border-slate-300 p-2 text-[12px] text-slate-800 focus:border-blue-500 focus:outline-none"
                placeholder="Type custom area here..."
                value={customArea}
                onChange={(e) => {
                  setCustomArea(e.target.value);
                  setSelectedAreaId(null);
                  setError(null);
                }}
              />
            </div>
          </section>

          {analysis.evidence.length ? (
            <section className="processor-section">
              <div className="processor-section-heading">
                <span className="processor-section-icon">
                  <Database className="h-4 w-4" />
                </span>
                <div>
                  <h3>3. Historical Evidence</h3>
                  <p>
                    Cases retrieved by the RAG pipeline and used as context.
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                {analysis.evidence.map((item) => (
                  <div
                    key={item.ticket_id}
                    className="rounded-xl border border-slate-200 bg-white p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <strong className="text-[10.5px] text-slate-700">
                        {item.ticket_id}
                      </strong>
                      {confidenceLabel(item.similarity) ? (
                        <span className="text-[9px] font-bold text-blue-600">
                          Similarity {confidenceLabel(item.similarity)}
                        </span>
                      ) : null}
                    </div>
                    {item.summary ? (
                      <p className="mt-1 text-[10.5px] font-semibold text-slate-600">
                        {item.summary}
                      </p>
                    ) : null}
                    {item.resolution_excerpt ? (
                      <p className="mt-1 text-[10px] leading-4 text-slate-500">
                        {item.resolution_excerpt}
                      </p>
                    ) : null}
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          <section className="processor-submit-card">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <ClipboardCheck className="h-4 w-4 text-blue-700" />
                <strong>Human review checkpoint</strong>
              </div>
              {/* MODIFICADO: Mensaje adaptado para no exigir la valoración */}
              <p>
                {isComplete
                  ? "Review complete. Send the validated feedback to the backend."
                  : `Complete ${hasResolution ? "" : "a selected or real solution, "}${hasAreaDecision ? "" : "and the affected area"}`}
              </p>
              {error ? <p className="processor-error">{error}</p> : null}
            </div>
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!isComplete || sending}
              className="processor-send-button"
            >
              <Send className="h-4 w-4" />
              {sending ? "Sending..." : "Send feedback"}
            </button>
          </section>
        </>
      )}
    </div>
  );
}

export function TicketOverview({
  tickets,
  totalLoaded,
  selectedTicket,
  onSelectTicket,
  onProcessed,
  analyses,
  analysisStatuses,
  onRetryAnalysis,
}: {
  tickets: Ticket[];
  totalLoaded: number;
  selectedTicket: Ticket | null;
  onSelectTicket: (ticket: Ticket | null) => void;
  onProcessed: (ticket: Ticket, record: ProcessedTicketRecord) => void;
  analyses: Record<string, TriageResult>;
  analysisStatuses: Record<string, TicketAnalysisStatus>;
  onRetryAnalysis: (ticket: Ticket) => Promise<void>;
}) {
  const categoryScroller = useRef<HTMLDivElement | null>(null);

  const analyzedTickets = useMemo(
    () =>
      tickets
        .filter(
          (ticket) =>
            analysisStatuses[ticket.issue_id] === "success" &&
            analyses[ticket.issue_id],
        )
        .sort(
          (a, b) =>
            priorityRank(analyses[a.issue_id]?.analysis.priority.value) -
            priorityRank(analyses[b.issue_id]?.analysis.priority.value),
        ),
    [tickets, analyses, analysisStatuses],
  );

  const analyzingCount = tickets.filter((ticket) =>
    ["queued", "analyzing"].includes(
      analysisStatuses[ticket.issue_id] ?? "idle",
    ),
  ).length;
  const errorCount = tickets.filter(
    (ticket) => analysisStatuses[ticket.issue_id] === "error",
  ).length;

  const categories = useMemo<CategoryCard[]>(
    () => [
      {
        title: "AI Priority",
        subtitle: "Calculated after AI triage",
        groups: buildGroups(analyzedTickets, (ticket) => [
          analyses[ticket.issue_id]?.analysis.priority.value,
        ]),
      },
      {
        title: "Work type",
        subtitle: "AI classification",
        groups: buildGroups(analyzedTickets, (ticket) => [
          analyses[ticket.issue_id]?.analysis.work_type.value,
        ]),
      },
      {
        title: "Affected service",
        subtitle: "Service inferred by AI",
        groups: buildGroups(analyzedTickets, (ticket) => [
          analyses[ticket.issue_id]?.analysis.affected_service.value,
        ]),
      },
      {
        title: "Service team",
        subtitle: "AI routing recommendation",
        groups: buildGroups(analyzedTickets, (ticket) => [
          analyses[ticket.issue_id]?.analysis.service_team.value,
        ]),
      },
      {
        title: "Assignee",
        subtitle: "AI routing recommendation",
        groups: buildGroups(analyzedTickets, (ticket) => [
          analyses[ticket.issue_id]?.analysis.assignee.value,
        ]),
      },
      {
        title: "Business entity",
        subtitle: "Original business context",
        groups: buildGroups(analyzedTickets, (ticket) => [
          ticket.business_entity,
        ]),
      },
    ],
    [analyzedTickets, analyses],
  );

  const scrollCategories = (direction: -1 | 1) =>
    categoryScroller.current?.scrollBy({
      left: direction * 390,
      behavior: "smooth",
    });

  if (selectedTicket) {
    return (
      <section className="panel-center min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-center">
          <div className="flex min-w-0 items-center gap-3">
            <span className="section-step section-step-center">02</span>
            <span className="section-icon section-icon-center">
              <ClipboardCheck className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h2 className="section-title">Process Ticket</h2>
              <p className="section-subtitle">
                Original information · AI analysis · human validation
              </p>
            </div>
          </div>
        </div>
        <TicketProcessor
          ticket={selectedTicket}
          analysis={analyses[selectedTicket.issue_id]}
          analysisStatus={analysisStatuses[selectedTicket.issue_id] ?? "idle"}
          onRetryAnalysis={() => onRetryAnalysis(selectedTicket)}
          onBack={() => onSelectTicket(null)}
          onProcessed={onProcessed}
        />
      </section>
    );
  }

  return (
    <section className="panel-center min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-center">
        <div className="flex min-w-0 items-center gap-3">
          <span className="section-step section-step-center">02</span>
          <span className="section-icon section-icon-center">
            <LayoutGrid className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <h2 className="section-title">AI-Organized Tickets</h2>
            <p className="section-subtitle">
              Categorized and ordered using the AI analysis, not the original
              benchmark priority
            </p>
          </div>
        </div>
        {totalLoaded > 0 ? (
          <span className="overview-chip">
            <Columns3 className="h-3.5 w-3.5" />
            {analyzedTickets.length.toLocaleString()} analyzed
          </span>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-4">
        {totalLoaded === 0 ? (
          <div className="flex min-h-full items-center justify-center">
            <div className="max-w-sm rounded-2xl border border-dashed border-blue-200 bg-blue-50/50 px-6 py-10 text-center">
              <LayoutGrid className="mx-auto h-7 w-7 text-blue-500" />
              <p className="mt-3 text-sm font-extrabold text-slate-800">
                Upload tickets to start automatic AI triage
              </p>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">
                The frontend extracts the official <code>records</code> array,
                keeps every raw ticket unchanged and sends each ticket to the
                backend.
              </p>
            </div>
          </div>
        ) : analyzedTickets.length === 0 ? (
          <div className="flex min-h-full items-center justify-center">
            <div className="max-w-md rounded-2xl border border-dashed border-blue-200 bg-blue-50/50 px-6 py-9 text-center">
              {analyzingCount ? (
                <LoaderCircle className="mx-auto h-7 w-7 animate-spin text-blue-500" />
              ) : (
                <TriangleAlert className="mx-auto h-7 w-7 text-amber-500" />
              )}
              <p className="mt-3 text-sm font-extrabold text-slate-800">
                {analyzingCount
                  ? "Analyzing uploaded tickets"
                  : "No AI-analyzed tickets available"}
              </p>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">
                {analyzingCount
                  ? `${analyzingCount} ticket(s) are waiting for the backend response.`
                  : `${errorCount} ticket(s) could not be analyzed. Open a ticket from the left queue to retry.`}
              </p>
            </div>
          </div>
        ) : (
          <section className="overview-block category-overview-block">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="overview-title">
                  Tickets categorized from AI output
                </h3>
                <p className="overview-copy">
                  Highest-priority AI results are processed first. Scroll
                  horizontally and click a ticket to compare original data with
                  the AI proposal.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {analyzingCount ? (
                  <span className="text-[10px] font-bold text-blue-600">
                    {analyzingCount} analyzing
                  </span>
                ) : null}
                {errorCount ? (
                  <span className="text-[10px] font-bold text-amber-600">
                    {errorCount} errors
                  </span>
                ) : null}
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => scrollCategories(-1)}
                    className="scroll-button"
                    aria-label="Scroll categories left"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <button
                    type="button"
                    onClick={() => scrollCategories(1)}
                    className="scroll-button"
                    aria-label="Scroll categories right"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>

            <div
              ref={categoryScroller}
              className="category-strip category-strip-tickets"
            >
              {categories.map((category) => (
                <article
                  key={category.title}
                  className="category-card category-card-tickets"
                >
                  <div className="category-card-title-row">
                    <div>
                      <h4>{category.title}</h4>
                      <p>{category.subtitle}</p>
                    </div>
                    <BrainCircuit className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
                  </div>
                  <div className="category-groups-scroll">
                    {category.groups.map((group) => (
                      <section
                        key={group.label}
                        className="category-ticket-group"
                      >
                        <div className="category-group-heading">
                          <strong>{group.label}</strong>
                          <span>{group.count.toLocaleString()}</span>
                        </div>
                        <div className="space-y-1.5">
                          {group.tickets.map((ticket) => (
                            <TicketChip
                              key={ticket.issue_id}
                              ticket={ticket}
                              analysis={analyses[ticket.issue_id]!}
                              onClick={() => onSelectTicket(ticket)}
                            />
                          ))}
                          {group.count > group.tickets.length ? (
                            <p className="category-more">
                              +{" "}
                              {(
                                group.count - group.tickets.length
                              ).toLocaleString()}{" "}
                              more tickets
                            </p>
                          ) : null}
                        </div>
                      </section>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}
      </div>
    </section>
  );
}
