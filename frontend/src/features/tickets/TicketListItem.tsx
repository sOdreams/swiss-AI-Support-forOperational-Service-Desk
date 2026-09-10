import { ChevronRight } from "lucide-react";
import { StatusBadge } from "../../components/StatusBadge";
import type { Ticket } from "../../types/ticket";

interface TicketListItemProps {
  ticket: Ticket;
  selected: boolean;
  onSelect: (ticket: Ticket) => void;
}

export function TicketListItem({ ticket, selected, onSelect }: TicketListItemProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(ticket)}
      aria-pressed={selected}
      className={`w-full border-b border-slate-200 px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-slate-500 ${
        selected ? "bg-slate-100" : "bg-white hover:bg-slate-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="font-mono text-xs font-semibold tracking-wide text-slate-500">
              {ticket.id}
            </span>
            <StatusBadge status={ticket.status} />
          </div>
          <p className="line-clamp-2 text-sm font-semibold leading-5 text-slate-900">
            {ticket.title}
          </p>
          {ticket.service ? (
            <p className="mt-2 truncate text-xs text-slate-500">{ticket.service}</p>
          ) : null}
        </div>
        <ChevronRight
          aria-hidden="true"
          className={`mt-1 h-4 w-4 shrink-0 ${selected ? "text-slate-700" : "text-slate-400"}`}
        />
      </div>
    </button>
  );
}
