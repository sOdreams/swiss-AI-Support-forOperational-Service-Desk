import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { mockTickets } from "./data/mockTickets";
import { TicketDetail } from "./features/tickets/TicketDetail";
import { TicketQueue } from "./features/tickets/TicketQueue";
import type { Ticket } from "./types/ticket";

export default function App() {
  const [selectedTicket, setSelectedTicket] = useState<Ticket | undefined>(mockTickets[0]);
  const [analysisNotice, setAnalysisNotice] = useState(false);

  const handleSelectTicket = (ticket: Ticket) => {
    setSelectedTicket(ticket);
    setAnalysisNotice(false);
  };

  const handleAnalyze = () => {
    setAnalysisNotice(true);
  };

  return (
    <div className="flex h-screen min-h-[640px] flex-col bg-slate-50 text-slate-900">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-900 text-white shadow-sm">
            <ShieldCheck aria-hidden="true" className="h-5 w-5" />
          </div>
          <div>
            <p className="text-base font-bold tracking-tight text-slate-950">Service Desk Copilot</p>
            <p className="text-xs text-slate-500">Swiss Life AI Support Assistant</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Prototype</p>
          <p className="text-xs text-slate-400">Analyst workspace</p>
        </div>
      </header>

      {analysisNotice ? (
        <div
          role="status"
          className="shrink-0 border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-900"
        >
          AI analysis is reserved for iteration F3. No backend or model request was made.
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1">
        <TicketQueue
          tickets={mockTickets}
          selectedTicketId={selectedTicket?.id}
          onSelectTicket={handleSelectTicket}
        />
        <TicketDetail ticket={selectedTicket} onAnalyze={handleAnalyze} />
      </div>
    </div>
  );
}
