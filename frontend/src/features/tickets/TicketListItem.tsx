import { ChevronRight } from "lucide-react";
import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import type { Ticket } from "../../types/ticket";

export function TicketListItem({ ticket, selected, onSelect }: { ticket: Ticket; selected: boolean; onSelect: (ticket: Ticket) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(ticket)}
      className={`group mx-3 mb-3 w-[calc(100%-24px)] rounded-2xl border px-4 py-4 text-left transition-all duration-150 ${
        selected
          ? "border-[#E7B98F] bg-white shadow-[0_10px_24px_rgba(178,93,39,0.12)] ring-2 ring-[#FFE3C5]"
          : "border-[#F1DCC7] bg-white/65 hover:-translate-y-0.5 hover:border-[#E8BF99] hover:bg-white hover:shadow-[0_8px_20px_rgba(178,93,39,0.08)]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-1 h-12 w-1.5 shrink-0 rounded-full ${selected ? "bg-[#D97735]" : "bg-[#F0D4B7] group-hover:bg-[#E6B584]"}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <span className={`font-mono text-[12px] font-extrabold ${selected ? "text-[#9A4F20]" : "text-slate-500"}`}>{ticket.issue_key}</span>
            <PriorityBadge priority={ticket.priority} />
          </div>
          <p className="mt-2 line-clamp-2 text-[14px] font-extrabold leading-5 text-slate-900">{ticket.summary}</p>
          <div className="mt-3 flex items-center justify-between gap-2">
            <StatusBadge status={ticket.status} />
            <span className="max-w-[170px] truncate text-[11px] font-medium text-slate-400">{ticket.service_teams[0] ?? "No service team"}</span>
          </div>
        </div>
        <ChevronRight className={`mt-1 h-4 w-4 shrink-0 transition-all group-hover:translate-x-0.5 ${selected ? "text-[#D97735]" : "text-slate-300"}`} />
      </div>
    </button>
  );
}
