import { ArrowRight, Database, FileSearch2, ShieldCheck, Sparkles, UserCheck } from "lucide-react";
import { useMemo, useState } from "react";
import { mockAiProposals } from "./data/mockAiProposals";
import { AiProposalPanel } from "./features/ai/AiProposalPanel";
import { TicketDetail } from "./features/tickets/TicketDetail";
import { TicketQueue } from "./features/tickets/TicketQueue";
import type { UploadState } from "./features/upload/TicketUpload";
import type { HumanReview } from "./types/review";
import type { Ticket } from "./types/ticket";

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicketId, setSelectedTicketId] = useState<string | undefined>(undefined);
  const [reviews, setReviews] = useState<Record<string, HumanReview>>({});
  const [uploadState, setUploadState] = useState<UploadState>({ fileName: null, error: null });

  const selectedTicket = useMemo(
    () => tickets.find((ticket) => ticket.issue_id === selectedTicketId),
    [tickets, selectedTicketId],
  );

  const proposal = useMemo(() => {
    if (!selectedTicket) return undefined;
    return mockAiProposals[selectedTicket.issue_id]
      ?? Object.values(mockAiProposals).find((item) => item.issue_key === selectedTicket.issue_key);
  }, [selectedTicket]);

  const selectedReview = selectedTicketId ? reviews[selectedTicketId] : undefined;
  const hasHumanDecision = Boolean(selectedReview && selectedReview.decision !== "pending");

  const handleLoaded = (loadedTickets: Ticket[], fileName: string) => {
    setTickets(loadedTickets);
    setSelectedTicketId(loadedTickets[0]?.issue_id);
    setReviews({});
    setUploadState({ fileName, error: null });
  };

  const handleUploadError = (fileName: string, message: string) => {
    setUploadState({ fileName, error: message });
  };

  return (
    <div className="app-shell h-screen overflow-auto text-[#172033]">
      <div className="flex min-h-[860px] min-w-[1500px] flex-col">
        <header className="app-header shrink-0">
          <div className="app-title-wrap">
            <div className="app-title-row">
              <span className="app-mark"><ShieldCheck className="h-6 w-6" /></span>
              <div className="text-center">
                <p className="app-kicker">SWISS {'{AI}'} WEEKS · SERVICE DESK PROTOTYPE</p>
                <h1 className="app-title">Service Desk Copilot</h1>
                <p className="app-subtitle">Evidence-backed triage with a human decision at the end of every recommendation</p>
              </div>
            </div>
          </div>

          <div className="workflow-bar" aria-label="Copilot workflow">
            <span className="workflow-caption">FLOW</span>
            <span className="workflow-step workflow-step-active"><Database className="h-3.5 w-3.5" />Ticket queue</span>
            <ArrowRight className="h-3.5 w-3.5 text-slate-300" />
            <span className={selectedTicket ? "workflow-step workflow-step-active" : "workflow-step"}><FileSearch2 className="h-3.5 w-3.5" />Original case</span>
            <ArrowRight className="h-3.5 w-3.5 text-slate-300" />
            <span className={proposal ? "workflow-step workflow-step-active" : "workflow-step"}><Sparkles className="h-3.5 w-3.5" />Evidence-backed AI</span>
            <ArrowRight className="h-3.5 w-3.5 text-slate-300" />
            <span className={hasHumanDecision ? "workflow-step workflow-step-complete" : "workflow-step"}><UserCheck className="h-3.5 w-3.5" />Human decision</span>
          </div>
        </header>

        <div className="workspace-grid min-h-0 flex-1">
          <TicketQueue
            tickets={tickets}
            selectedTicketId={selectedTicket?.issue_id}
            onSelectTicket={(ticket) => setSelectedTicketId(ticket.issue_id)}
            onTicketsLoaded={handleLoaded}
            onUploadError={handleUploadError}
            uploadState={uploadState}
          />
          <TicketDetail ticket={selectedTicket} />
          <AiProposalPanel
            ticket={selectedTicket}
            proposal={proposal}
            review={selectedReview}
            onReviewChange={(review) => setReviews((current) => ({ ...current, [review.ticket_id]: review }))}
          />
        </div>
      </div>
    </div>
  );
}
