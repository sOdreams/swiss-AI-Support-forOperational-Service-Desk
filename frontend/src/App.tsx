import { ArrowRight, Database, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { useMemo, useState } from "react";
import { mockAiProposals } from "./data/mockAiProposals";
import { mockTickets } from "./data/mockTickets";
import { AiProposalPanel } from "./features/ai/AiProposalPanel";
import { TicketDetail } from "./features/tickets/TicketDetail";
import { TicketQueue } from "./features/tickets/TicketQueue";
import type { HumanReview } from "./types/review";

export default function App() {
  const [selectedTicketId, setSelectedTicketId] = useState(mockTickets[0]?.issue_id);
  const [reviews, setReviews] = useState<Record<string, HumanReview>>({});
  const selectedTicket = useMemo(() => mockTickets.find((ticket) => ticket.issue_id === selectedTicketId), [selectedTicketId]);
  const proposal = selectedTicketId ? mockAiProposals[selectedTicketId] : undefined;

  return (
    <div className="flex h-screen min-h-[760px] min-w-[1280px] flex-col bg-[#EEF2F7] text-[#172033]">
      <header className="shrink-0 border-b border-slate-200 bg-white">
        <div className="flex h-[56px] items-center justify-between px-5">
          <div className="flex items-center gap-3"><div className="flex h-9 w-9 items-center justify-center rounded-md bg-blue-700 text-white"><ShieldCheck className="h-5 w-5" /></div><div><div className="flex items-center gap-2"><p className="text-sm font-bold text-slate-950">Service Desk Copilot</p><span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[9px] font-semibold text-blue-700">Jira + AI review</span></div><p className="text-[10px] text-slate-500">Original data stays separate from AI proposals and human decisions.</p></div></div>
          <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 py-1 pl-1 pr-3"><span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-700 text-white"><UserRound className="h-3.5 w-3.5" /></span><span className="text-[10px] font-semibold text-slate-700">Razon · Analyst</span></div>
        </div>
        <div className="flex h-[36px] items-center justify-center gap-2 border-t border-slate-100 bg-slate-50 px-4 text-[10px] text-slate-500">
          <span className="inline-flex items-center gap-1.5 font-semibold text-blue-700"><Database className="h-3 w-3" />1. Original ticket</span><ArrowRight className="h-3 w-3" /><span className="inline-flex items-center gap-1.5"><Sparkles className="h-3 w-3" />2. AI proposal</span><ArrowRight className="h-3 w-3" /><span>3. Approve, edit or reject</span>
        </div>
      </header>
      <div className="grid min-h-0 flex-1 overflow-hidden" style={{ gridTemplateColumns: "270px minmax(650px, 1fr) 380px" }}>
        <TicketQueue tickets={mockTickets} selectedTicketId={selectedTicket?.issue_id} onSelectTicket={(ticket) => setSelectedTicketId(ticket.issue_id)} />
        <TicketDetail ticket={selectedTicket} />
        <AiProposalPanel ticket={selectedTicket} proposal={proposal} review={selectedTicketId ? reviews[selectedTicketId] : undefined} onReviewChange={(review) => setReviews((current) => ({ ...current, [review.ticket_id]: review }))} />
      </div>
    </div>
  );
}
