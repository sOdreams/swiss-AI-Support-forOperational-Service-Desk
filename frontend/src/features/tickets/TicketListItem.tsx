import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import type { Ticket } from "../../types/ticket";

export function TicketListItem({ ticket, selected = false, onClick }: { ticket: Ticket; selected?: boolean; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`group mx-3 mb-2.5 block w-[calc(100%_-_1.5rem)] rounded-2xl border px-3 py-3 text-left transition-all duration-150 ${
        selected
          ? "border-[#D69C68] bg-white shadow-[0_8px_22px_rgba(178,93,39,0.12)]"
          : "border-[#F1DCC7] bg-white/72 hover:-translate-y-0.5 hover:border-[#E8BF99] hover:bg-white hover:shadow-[0_8px_20px_rgba(178,93,39,0.08)]"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-1 h-10 w-1 shrink-0 rounded-full transition ${selected ? "bg-[#C9783D]" : "bg-[#F0D4B7] group-hover:bg-[#E6B584]"}`} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <span className="font-mono text-[12px] font-extrabold text-slate-600">{ticket.issue_key}</span>
            <PriorityBadge priority={ticket.priority} />
          </div>
          <p className="mt-2 line-clamp-2 text-[12.5px] font-extrabold leading-4.5 text-slate-900">{ticket.summary}</p>
          <div className="mt-2.5 flex items-center justify-between gap-2">
            <StatusBadge status={ticket.status} />
            <span className="max-w-[150px] truncate text-[10px] font-medium text-slate-400">{ticket.service_teams[0] ?? "No service team"}</span>
          </div>
        </div>
      </div>
    </button>
  );
}
