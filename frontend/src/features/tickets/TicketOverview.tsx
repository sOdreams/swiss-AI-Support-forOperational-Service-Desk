import {
  ArrowLeft,
  Building2,
  Check,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Columns3,
  LayoutGrid,
  Send,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { RetrievalEvidencePanel } from "../retrieval/RetrievalEvidencePanel";
import { useRetrieval } from "../retrieval/useRetrieval";
import { useTicketAnalysis } from "../analysis/useTicketAnalysis";
import { TicketAnalysisPanel } from "../analysis/TicketAnalysisPanel";
import { submitProcessedTicket } from "../../services/api";
import type { ProcessedTicketRecord, ProcessTicketPayload } from "../../types/processing";
import type { Ticket } from "../../types/ticket";

const TICKETS_PER_GROUP = 6;
const GROUPS_PER_CATEGORY = 5;

type CategoryGroup = {
  label: string;
  count: number;
  tickets: Ticket[];
};

type CategoryCard = {
  title: string;
  subtitle: string;
  groups: CategoryGroup[];
};

function normalizeLabel(value: string | null | undefined) {
  return value?.trim() || "Not recorded";
}

function buildGroups(tickets: Ticket[], getValues: (ticket: Ticket) => Array<string | null | undefined>): CategoryGroup[] {
  const groups = new Map<string, Ticket[]>();

  for (const ticket of tickets) {
    const values = getValues(ticket);
    const normalized = values.length ? values.map(normalizeLabel) : ["Not recorded"];
    for (const label of [...new Set(normalized)]) {
      const current = groups.get(label) ?? [];
      current.push(ticket);
      groups.set(label, current);
    }
  }

  return [...groups.entries()]
    .sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
    .slice(0, GROUPS_PER_CATEGORY)
    .map(([label, groupTickets]) => ({ label, count: groupTickets.length, tickets: groupTickets.slice(0, TICKETS_PER_GROUP) }));
}

function recommendedSolutions(ticket: Ticket) {
  const primaryService = ticket.affected_business_or_it_services[0] ?? ticket.service_teams[0] ?? "the affected service";
  const team = ticket.service_teams[0] ?? "the owning support team";

  return [
    `Validate the reported symptoms for ${primaryService}, reproduce the issue where possible, and confirm whether the failure is caused by access, configuration, or service availability.`,
    `Route or escalate the case to ${team} with priority, urgency, impact, linked issues, and all analyst findings included so the next team can act without repeating triage.`,
    `Apply the relevant documented troubleshooting procedure for ${primaryService}, verify the result with the requester, and only resolve the ticket after the expected service is confirmed working.`,
  ];
}

function businessAspects(ticket: Ticket) {
  const service = ticket.affected_business_or_it_services[0] ?? "the affected service";
  const entity = ticket.business_entity ?? "the affected business area";

  return [
    `Service continuity — availability, reliability, or access to ${service}.`,
    `Business productivity — users in ${entity} are blocked, delayed, or working with reduced capability.`,
    ticket.business_critical_for_entity
      ? "Critical business / regulatory impact — disruption may affect time-sensitive, financial, compliance, or executive processes."
      : "Operational / customer impact — downstream delivery, service quality, or customer-facing work may be affected.",
  ];
}

function TicketChip({ ticket, onClick }: { ticket: Ticket; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="category-ticket-button" title={`${ticket.issue_key} — ${ticket.summary}`}>
      <span className="font-mono">{ticket.issue_key}</span>
      <span className="truncate">{ticket.summary}</span>
      <ChevronRight className="h-3.5 w-3.5 shrink-0" />
    </button>
  );
}

function TicketProcessor({ ticket, onBack, onProcessed }: {
  ticket: Ticket;
  onBack: () => void;
  onProcessed: (ticket: Ticket, record: ProcessedTicketRecord) => void;
}) {
  const originalRetrieval = useRetrieval(ticket);
  const analysis = useTicketAnalysis(ticket);
  const retrieval = analysis.data?.retrieval ? { data: analysis.data.retrieval, loading: false, error: null } : originalRetrieval;
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
  const solutions = useMemo(() => recommendedSolutions(ticket), [ticket]);
  const aspects = useMemo(() => businessAspects(ticket), [ticket]);
  const [selectedSolution, setSelectedSolution] = useState<string | null>(null);
  const [realSolution, setRealSolution] = useState("");
  const [selectedAspect, setSelectedAspect] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSelectedEvidenceIds([]);
    setSelectedSolution(null);
    setRealSolution("");
    setSelectedAspect(null);
    setError(null);
  }, [ticket.issue_id]);

  const hasSolution = Boolean(selectedSolution || realSolution.trim());
  const isComplete = hasSolution && Boolean(selectedAspect);

  const toggleSolution = (solution: string) => {
    setSelectedSolution((current) => current === solution ? null : solution);
    setError(null);
  };

  const handleSend = async () => {
    if (!isComplete || !selectedAspect) {
      setError("Complete the solution and affected business aspect before sending.");
      return;
    }

    setSending(true);
    setError(null);
    const processedAt = new Date().toISOString();
    const payload: ProcessTicketPayload = {
      issue_id: ticket.issue_id,
      issue_key: ticket.issue_key,
      recommended_solution: selectedSolution,
      real_solution: realSolution.trim() || null,
      affected_business_aspect: selectedAspect,
      processed_at: processedAt,
      source: "human_resolution_workflow",
      ...(retrieval.data ? { retrieval: {
        index_version: retrieval.data.index_version,
        model: retrieval.data.model,
        shown_document_ids: retrieval.data.hits.map((hit) => hit.document_id),
        selected_document_ids: selectedEvidenceIds,
      } } : {}),
    };

    let syncStatus: ProcessedTicketRecord["sync_status"] = "api";

    try {
      await submitProcessedTicket(payload);
    } catch {
      try {
        const key = "service-desk-copilot-processed-feedback";
        const stored = JSON.parse(localStorage.getItem(key) ?? "[]") as ProcessTicketPayload[];
        localStorage.setItem(key, JSON.stringify([...stored, payload]));
        syncStatus = "local";
      } catch {
        setSending(false);
        setError("The ticket could not be saved. Please try again.");
        return;
      }
    }

    const record: ProcessedTicketRecord = {
      issue_id: ticket.issue_id,
      issue_key: ticket.issue_key,
      summary: ticket.summary,
      recommended_solution: selectedSolution,
      real_solution: realSolution.trim() || null,
      affected_business_aspect: selectedAspect,
      processed_at: processedAt,
      sync_status: syncStatus,
    };

    onProcessed(ticket, record);
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-4">
      <button type="button" onClick={onBack} className="processor-back-button"><ArrowLeft className="h-3.5 w-3.5" />Back to categories</button>

      <section className="processor-ticket-hero">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px] font-black text-blue-700">{ticket.issue_key}</span>
              <PriorityBadge priority={ticket.priority} />
              <StatusBadge status={ticket.status} />
            </div>
            <h2 className="mt-2 text-[17px] font-black leading-6 text-slate-900">{ticket.summary}</h2>
          </div>
        </div>
        <p className="mt-3 text-[11px] leading-5 text-slate-600">{ticket.description || "No description recorded."}</p>

        <div className="processor-info-grid">
          <div><span>Work type</span><strong>{ticket.work_type ?? "Not recorded"}</strong></div>
          <div><span>Request type</span><strong>{ticket.request_type ?? "Not recorded"}</strong></div>
          <div><span>Priority</span><strong>{ticket.priority ?? "Not recorded"}</strong></div>
          <div><span>Status</span><strong>{ticket.status}</strong></div>
          <div><span>Business entity</span><strong>{ticket.business_entity ?? "Not recorded"}</strong></div>
          <div><span>Service team</span><strong>{ticket.service_teams.join(", ") || "Not recorded"}</strong></div>
          <div><span>Urgency</span><strong>{ticket.urgency ?? "Not recorded"}</strong></div>
          <div><span>Impact</span><strong>{ticket.impact ?? "Not recorded"}</strong></div>
        </div>
      </section>

      <TicketAnalysisPanel ticket={ticket} data={analysis.data} loading={analysis.loading} error={analysis.error} onRun={analysis.run} />
      <RetrievalEvidencePanel {...retrieval} filter={analysis.data?.filter} selectedIds={selectedEvidenceIds} onToggle={(id) => {
        setSelectedEvidenceIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
      }} />

      <section className="processor-section">
        <div className="processor-section-heading">
          <span className="processor-section-icon"><Wrench className="h-4 w-4" /></span>
          <div><h3>1. Suggested review steps</h3><p>These are general templates. Review the evidence above, or write the actual solution below.</p></div>
        </div>
        <div className="recommendation-scroll">
          {solutions.map((solution, index) => {
            const selected = selectedSolution === solution;
            return (
              <button key={solution} type="button" onClick={() => toggleSolution(solution)} className={`recommendation-option ${selected ? "recommendation-option-selected" : ""}`}>
                <span className="recommendation-number">{index + 1}</span>
                <span className="flex-1">{solution}</span>
                <span className="recommendation-check">{selected ? <Check className="h-4 w-4" /> : null}</span>
              </button>
            );
          })}
        </div>

        <div className="real-solution-wrap">
          <label htmlFor="real-solution">1.2 Real solution <span>{selectedSolution ? "optional" : "required if no recommendation is selected"}</span></label>
          <textarea
            id="real-solution"
            value={realSolution}
            onChange={(event) => { setRealSolution(event.target.value); setError(null); }}
            rows={4}
            placeholder="Write the actual solution applied by the analyst. This is captured as human feedback for AI evaluation and future learning."
          />
        </div>
      </section>

      <section className="processor-section">
        <div className="processor-section-heading">
          <span className="processor-section-icon processor-section-icon-business"><Building2 className="h-4 w-4" /></span>
          <div><h3>2. Affected Business Aspect</h3><p>Select the business impact that best represents this ticket.</p></div>
        </div>
        <div className="business-aspect-grid">
          {aspects.map((aspect, index) => {
            const selected = selectedAspect === aspect;
            return (
              <button key={aspect} type="button" onClick={() => { setSelectedAspect(aspect); setError(null); }} className={`business-aspect-option ${selected ? "business-aspect-option-selected" : ""}`}>
                <span className="business-aspect-number">{index + 1}</span>
                <span>{aspect}</span>
                {selected ? <Check className="ml-auto h-4 w-4 shrink-0" /> : null}
              </button>
            );
          })}
        </div>
      </section>

      <section className="processor-submit-card">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><ClipboardCheck className="h-4 w-4 text-blue-700" /><strong>Ready to process</strong></div>
          <p>{isComplete ? "All required information is complete. Sending will move this ticket to Processed Tickets." : "Choose a solution (or enter the real solution) and select one affected business aspect."}</p>
          {error ? <p className="processor-error">{error}</p> : null}
        </div>
        <button type="button" onClick={() => void handleSend()} disabled={!isComplete || sending} className="processor-send-button">
          <Send className="h-4 w-4" />{sending ? "Sending..." : "Send"}
        </button>
      </section>
    </div>
  );
}

export function TicketOverview({
  tickets,
  totalLoaded,
  selectedTicket,
  onSelectTicket,
  onProcessed,
}: {
  tickets: Ticket[];
  totalLoaded: number;
  selectedTicket: Ticket | null;
  onSelectTicket: (ticket: Ticket | null) => void;
  onProcessed: (ticket: Ticket, record: ProcessedTicketRecord) => void;
}) {
  const categoryScroller = useRef<HTMLDivElement | null>(null);

  const categories = useMemo<CategoryCard[]>(() => [
    { title: "Work type", subtitle: "What kind of work is this?", groups: buildGroups(tickets, (ticket) => [ticket.work_type]) },
    { title: "Request type", subtitle: "How is the request classified?", groups: buildGroups(tickets, (ticket) => [ticket.request_type]) },
    { title: "Priority", subtitle: "Recorded operational priority", groups: buildGroups(tickets, (ticket) => [ticket.priority]) },
    { title: "Status", subtitle: "Where the work currently is", groups: buildGroups(tickets, (ticket) => [ticket.status]) },
    { title: "Service team", subtitle: "Current ownership and routing", groups: buildGroups(tickets, (ticket) => ticket.service_teams.length ? ticket.service_teams : [null]) },
    { title: "Business entity", subtitle: "Which business area is affected?", groups: buildGroups(tickets, (ticket) => [ticket.business_entity]) },
  ], [tickets]);

  const scrollCategories = (direction: -1 | 1) => {
    categoryScroller.current?.scrollBy({ left: direction * 390, behavior: "smooth" });
  };

  if (selectedTicket) {
    return (
      <section className="panel-center min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-center">
          <div className="flex min-w-0 items-center gap-3">
            <span className="section-step section-step-center">02</span>
            <span className="section-icon section-icon-center"><ClipboardCheck className="h-4 w-4" /></span>
            <div className="min-w-0"><h2 className="section-title">Process Ticket</h2><p className="section-subtitle">Review, resolve and capture structured human feedback</p></div>
          </div>
        </div>
        <TicketProcessor key={selectedTicket.issue_id} ticket={selectedTicket} onBack={() => onSelectTicket(null)} onProcessed={onProcessed} />
      </section>
    );
  }

  return (
    <section className="panel-center min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-center">
        <div className="flex min-w-0 items-center gap-3">
          <span className="section-step section-step-center">02</span>
          <span className="section-icon section-icon-center"><LayoutGrid className="h-4 w-4" /></span>
          <div className="min-w-0">
            <h2 className="section-title">Ticket Categories</h2>
            <p className="section-subtitle">Open tickets directly from the category view</p>
          </div>
        </div>
        {totalLoaded > 0 ? <span className="overview-chip"><Columns3 className="h-3.5 w-3.5" />{tickets.length.toLocaleString()} active</span> : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-4">
        {totalLoaded === 0 ? (
          <div className="flex min-h-full items-center justify-center">
            <div className="max-w-sm rounded-2xl border border-dashed border-blue-200 bg-blue-50/50 px-6 py-10 text-center">
              <LayoutGrid className="mx-auto h-7 w-7 text-blue-500" />
              <p className="mt-3 text-sm font-extrabold text-slate-800">Upload tickets to build the category view</p>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">Tickets will be grouped into scrollable category columns. Click any ticket to start processing it.</p>
            </div>
          </div>
        ) : tickets.length === 0 ? (
          <div className="flex min-h-full items-center justify-center">
            <div className="max-w-sm rounded-2xl border border-dashed border-blue-200 bg-blue-50/50 px-6 py-10 text-center">
              <Sparkles className="mx-auto h-7 w-7 text-blue-500" />
              <p className="mt-3 text-sm font-extrabold text-slate-800">No active tickets in this view</p>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">Adjust the Ticket Queue filters or upload a new JSON file.</p>
            </div>
          </div>
        ) : (
          <section className="overview-block category-overview-block">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="overview-title">Active tickets by category</h3>
                <p className="overview-copy">Scroll horizontally. Each ticket is clickable and opens the resolution workflow.</p>
              </div>
              <div className="flex gap-1.5">
                <button type="button" onClick={() => scrollCategories(-1)} className="scroll-button" aria-label="Scroll categories left"><ChevronLeft className="h-4 w-4" /></button>
                <button type="button" onClick={() => scrollCategories(1)} className="scroll-button" aria-label="Scroll categories right"><ChevronRight className="h-4 w-4" /></button>
              </div>
            </div>

            <div ref={categoryScroller} className="category-strip category-strip-tickets">
              {categories.map((category) => (
                <article key={category.title} className="category-card category-card-tickets">
                  <div className="category-card-title-row">
                    <div><h4>{category.title}</h4><p>{category.subtitle}</p></div>
                    <Columns3 className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
                  </div>

                  <div className="category-groups-scroll">
                    {category.groups.map((group) => (
                      <section key={group.label} className="category-ticket-group">
                        <div className="category-group-heading"><strong>{group.label}</strong><span>{group.count.toLocaleString()}</span></div>
                        <div className="space-y-1.5">
                          {group.tickets.map((ticket) => <TicketChip key={ticket.issue_id} ticket={ticket} onClick={() => onSelectTicket(ticket)} />)}
                          {group.count > group.tickets.length ? <p className="category-more">+ {(group.count - group.tickets.length).toLocaleString()} more tickets</p> : null}
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
