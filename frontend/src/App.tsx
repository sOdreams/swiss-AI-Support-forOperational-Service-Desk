import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { ProcessedTicketsPanel } from "./features/ai/ProcessedTicketsPanel";
import { TicketOverview } from "./features/tickets/TicketOverview";
import { TicketQueue } from "./features/tickets/TicketQueue";
import type { UploadState } from "./features/upload/TicketUpload";
import type { ProcessedTicketRecord } from "./types/processing";
import type { Ticket } from "./types/ticket";

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [queueViewTickets, setQueueViewTickets] = useState<Ticket[]>([]);
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [processedTickets, setProcessedTickets] = useState<ProcessedTicketRecord[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>({ fileName: null, error: null });

  const handleLoaded = (loadedTickets: Ticket[], fileName: string) => {
    setTickets(loadedTickets);
    setQueueViewTickets(loadedTickets);
    setSelectedTicket(null);
    setProcessedTickets([]);
    setUploadState({ fileName, error: null });
  };

  const handleUploadError = (fileName: string, message: string) => {
    setUploadState({ fileName, error: message });
  };

  const handleProcessed = (ticket: Ticket, record: ProcessedTicketRecord) => {
    setTickets((current) => current.filter((item) => item.issue_id !== ticket.issue_id));
    setQueueViewTickets((current) => current.filter((item) => item.issue_id !== ticket.issue_id));
    setProcessedTickets((current) => [record, ...current]);
    setSelectedTicket(null);
  };

  const activeTickets = tickets.length === 0 ? [] : queueViewTickets;

  return (
    <div className="app-shell h-[100dvh] overflow-hidden text-[#172033]">
      <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
        <header className="app-header shrink-0">
          <div className="app-title-wrap app-title-wrap-compact">
            <div className="app-title-row">
              <span className="app-mark app-mark-compact"><ShieldCheck className="h-5 w-5" /></span>
              <div className="text-center">
                <p className="app-kicker">SWISS {'{AI}'} WEEKS · SERVICE DESK PROTOTYPE</p>
                <h1 className="app-title app-title-compact">Service Desk Copilot</h1>
                <p className="app-subtitle">Review tickets · capture real resolutions · build better AI feedback</p>
              </div>
            </div>
          </div>
        </header>

        <main className="workspace-grid min-h-0 flex-1">
          <TicketQueue
            tickets={tickets}
            selectedTicketId={selectedTicket?.issue_id ?? null}
            onSelectTicket={setSelectedTicket}
            onFilteredTicketsChange={setQueueViewTickets}
            onTicketsLoaded={handleLoaded}
            onUploadError={handleUploadError}
            uploadState={uploadState}
          />
          <TicketOverview
            tickets={activeTickets}
            totalLoaded={tickets.length}
            selectedTicket={selectedTicket}
            onSelectTicket={setSelectedTicket}
            onProcessed={handleProcessed}
          />
          <ProcessedTicketsPanel tickets={processedTickets} />
        </main>
      </div>
    </div>
  );
}
