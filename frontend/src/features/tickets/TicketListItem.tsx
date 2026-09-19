import { ChevronRight } from "lucide-react";
import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDate } from "../../lib/utils";
import type { Ticket } from "../../types/ticket";

export function TicketListItem({ ticket, selected, onSelect }: { ticket: Ticket; selected: boolean; onSelect: (ticket: Ticket) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(ticket)}
      className={`w-full border-b border-slate-100 px-3.5 py-3 text-left transition ${selected ? "border-l-[3px] border-l-blue-600 bg-blue-50/70" : "bg-[#F7F9FC] hover:bg-white"}`}
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-[10px] font-bold text-slate-500">{ticket.issue_key}</span>
            <PriorityBadge priority={ticket.priority} />
          </div>
          <p className="mt-1.5 line-clamp-2 text-[12px] font-semibold leading-5 text-slate-900">{ticket.summary}</p>
          <div className="mt-2 flex items-center gap-2">
            <StatusBadge status={ticket.status} />
            <span className="truncate text-[10px] text-slate-400">{ticket.service_teams[0] ?? "No team"}</span>
          </div>
          <p className="mt-1.5 text-[9px] text-slate-400">Created {formatDate(ticket.created_date)}</p>
        </div>
        <ChevronRight className={`mt-1 h-4 w-4 ${selected ? "text-blue-600" : "text-slate-300"}`} />
      </div>
    </button>
  );
}
