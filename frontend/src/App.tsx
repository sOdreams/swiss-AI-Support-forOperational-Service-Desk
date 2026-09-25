import { AlertTriangle, Database, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { AiProposalPanel } from "./features/ai/AiProposalPanel";
import { TicketDetail } from "./features/tickets/TicketDetail";
import { TicketQueue } from "./features/tickets/TicketQueue";
import type { UploadState } from "./features/upload/TicketUpload";
import { analyzeTicket, getTickets, importTickets, saveHumanReview } from "./services/api";
import type { AiProposal } from "./types/ai";
import type { HumanReview } from "./types/review";
import type { Ticket } from "./types/ticket";

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [proposal, setProposal] = useState<AiProposal | undefined>();
  const [review, setReview] = useState<HumanReview | undefined>();
  const [uploadState, setUploadState] = useState<UploadState>({ fileName: null, error: null });
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [savedReviews, setSavedReviews] = useState(0);

  const loadTickets = useCallback(async () => {
    setLoading(true);
    try {
      const loadedTickets = await getTickets();
      setTickets(loadedTickets);
      setSelectedTicket((current) => current && loadedTickets.some((ticket) => ticket.issue_id === current.issue_id) ? current : loadedTickets[0] ?? null);
      setConnectionError(null);
      setUploadState({ fileName: "SwissLife challenge queue", error: null });
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "The triage service is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadTickets(); }, [loadTickets]);

  useEffect(() => {
    if (!selectedTicket) {
      setProposal(undefined);
      setReview(undefined);
      return;
    }
    let cancelled = false;
    setAnalyzing(true);
    setProposal(undefined);
    setReview(undefined);
    void analyzeTicket(selectedTicket.issue_id)
      .then((nextProposal) => { if (!cancelled) setProposal(nextProposal); })
      .catch((error) => { if (!cancelled) setConnectionError(error instanceof Error ? error.message : "Ticket analysis failed."); })
      .finally(() => { if (!cancelled) setAnalyzing(false); });
    return () => { cancelled = true; };
  }, [selectedTicket]);

  const handleLoaded = async (loadedTickets: Ticket[], fileName: string) => {
    setTickets(loadedTickets);
    setSelectedTicket(loadedTickets[0] ?? null);
    setUploadState({ fileName, error: null });
    try {
      const imported = await importTickets(loadedTickets);
      setTickets(imported.tickets);
      setSelectedTicket(imported.tickets[0] ?? null);
      setConnectionError(null);
    } catch {
      // The local queue remains usable even if the backend cannot accept an upload.
      setUploadState({ fileName, error: "Loaded locally; reconnect the triage service to enable AI analysis." });
    }
  };

  const handleUploadError = (fileName: string, message: string) => {
    setUploadState({ fileName, error: message });
  };

  const handleReviewChange = (nextReview: HumanReview) => {
    setReview(nextReview);
    setSavedReviews((current) => current + 1);
    void saveHumanReview(nextReview).catch(() => {
      setConnectionError("The decision is visible locally, but could not be saved to the backend.");
    });
  };

  return (
    <div className="app-shell h-[100dvh] overflow-hidden text-[#172033]">
      <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
        <header className="app-header shrink-0">
          <div className="app-title-wrap app-title-wrap-compact">
            <div className="app-title-row">
              <span className="app-mark app-mark-compact"><ShieldCheck className="h-5 w-5" /></span>
              <div className="text-center">
                <p className="app-kicker">SWISSLIFE · AI-ASSISTED SERVICE DESK</p>
                <h1 className="app-title app-title-compact">Triage Workbench</h1>
                <p className="app-subtitle">Evidence-led routing with human approval at every decision</p>
              </div>
            </div>
            <div className="app-header-status">
              <span className={`connection-pill ${connectionError ? "connection-pill-error" : ""}`}>
                {connectionError ? <AlertTriangle className="h-3.5 w-3.5" /> : <Database className="h-3.5 w-3.5" />}
                {connectionError ? "Service offline" : "Engine connected"}
              </span>
              <span className="header-stat"><Sparkles className="h-3.5 w-3.5" />{savedReviews} reviews saved</span>
              <button type="button" onClick={() => void loadTickets()} className="header-refresh" disabled={loading} title="Reload ticket queue">
                <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>
        </header>

        <main className="workspace-grid min-h-0 flex-1">
          <TicketQueue
            tickets={tickets}
            selectedTicketId={selectedTicket?.issue_id ?? null}
            onSelectTicket={setSelectedTicket}
            onFilteredTicketsChange={() => undefined}
            onTicketsLoaded={handleLoaded}
            onUploadError={handleUploadError}
            uploadState={uploadState}
          />
          {loading && tickets.length === 0 ? (
            <main className="panel-center min-h-0 min-w-0 overflow-hidden"><div className="empty-state"><RefreshCw className="h-6 w-6 animate-spin text-blue-600" /><p>Loading the SwissLife queue…</p><span>Preparing the evidence-backed workspace.</span></div></main>
          ) : connectionError && tickets.length === 0 ? (
            <main className="panel-center min-h-0 min-w-0 overflow-hidden"><div className="empty-state empty-state-error"><AlertTriangle className="h-6 w-6 text-amber-600" /><p>Connect the triage service to begin</p><span>Start the local service, then press reload. You can still upload a JSON file from the queue.</span><button type="button" onClick={() => void loadTickets()} className="empty-state-button">Try again</button></div></main>
          ) : (
            <TicketDetail
              ticket={selectedTicket ?? undefined}
              proposal={analyzing ? undefined : proposal}
              review={review}
              onReviewChange={handleReviewChange}
            />
          )}
          <AiProposalPanel ticket={selectedTicket ?? undefined} proposal={analyzing ? undefined : proposal} review={review} />
        </main>
      </div>
    </div>
  );
}
