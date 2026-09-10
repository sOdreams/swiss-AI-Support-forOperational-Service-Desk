import { Inbox } from "lucide-react";
import type { Ticket } from "../../types/ticket";
import { TicketListItem } from "./TicketListItem";

interface TicketQueueProps {
  tickets: Ticket[];
  selectedTicketId?: string;
  onSelectTicket: (ticket: Ticket) => void;
}

export function TicketQueue({
  tickets,
  selectedTicketId,
  onSelectTicket,
}: TicketQueueProps) {
  return (
    <aside className="flex min-h-0 w-[300px] shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-4">
        <div className="flex items-center gap-2">
          <Inbox aria-hidden="true" className="h-4 w-4 text-slate-500" />
          <h2 className="text-sm font-bold uppercase tracking-[0.08em] text-slate-700">
            Ticket Queue
          </h2>
        </div>
        <p className="mt-1 text-xs text-slate-500">{tickets.length} active demo tickets</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tickets.map((ticket) => (
          <TicketListItem
            key={ticket.id}
            ticket={ticket}
            selected={ticket.id === selectedTicketId}
            onSelect={onSelectTicket}
          />
        ))}
      </div>
    </aside>
  );
}
