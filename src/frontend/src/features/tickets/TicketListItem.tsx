import { Building2, CalendarDays, LoaderCircle, Sparkles, TriangleAlert } from "lucide-react";
import { StatusBadge } from "../../components/StatusBadge";
import type { Ticket } from "../../types/ticket";
import type { TicketAnalysisStatus } from "../../types/triage";

function shortDate(value: string) {
  if (!value) return null;
  const parsed = new Date(value.replace(" ", "T"));
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en", { day: "2-digit", month: "short" }).format(parsed);
}

function AnalysisState({ status }: { status: TicketAnalysisStatus }) {
  if (status === "analyzing" || status === "queued") {
    return <span className="inline-flex items-center gap-1 text-[9.5px] font-bold text-blue-600"><LoaderCircle className="h-3 w-3 animate-spin" />AI analyzing</span>;
  }
  if (status === "success") {
    return <span className="inline-flex items-center gap-1 text-[9.5px] font-bold text-emerald-700"><Sparkles className="h-3 w-3" />AI ready</span>;
  }
  if (status === "error") {
    return <span className="inline-flex items-center gap-1 text-[9.5px] font-bold text-amber-700"><TriangleAlert className="h-3 w-3" />AI unavailable</span>;
  }
  return null;
}

export function TicketListItem({
  ticket,
  selected = false,
  onClick,
  analysisStatus = "idle",
}: {
  ticket: Ticket;
  selected?: boolean;
  onClick?: () => void;
  analysisStatus?: TicketAnalysisStatus;
}) {
  const service = ticket.affected_business_or_it_services[0] ?? null;
  const created = shortDate(ticket.created_date);

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
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-[10px] font-black uppercase tracking-[0.08em] text-[#9A6C48]">{ticket.work_type ?? "Ticket"}</p>
              {ticket.request_type ? <p className="mt-0.5 truncate text-[10px] font-semibold text-slate-400">{ticket.request_type}</p> : null}
            </div>
            <AnalysisState status={analysisStatus} />
          </div>

          <p className="mt-2 line-clamp-2 text-[12.5px] font-extrabold leading-4.5 text-slate-900">{ticket.summary}</p>

          <div className="mt-2.5 space-y-1.5 text-[10px] text-slate-500">
            {service ? <div className="truncate font-semibold text-slate-600">{service}</div> : null}
            <div className="flex min-w-0 items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-1.5 truncate">
                <Building2 className="h-3 w-3 shrink-0 text-slate-400" />
                <span className="truncate">{ticket.business_entity ?? "Business entity not recorded"}</span>
              </span>
              {created ? <span className="flex shrink-0 items-center gap-1 text-slate-400"><CalendarDays className="h-3 w-3" />{created}</span> : null}
            </div>
          </div>

          <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-[#F1E7DE] pt-2">
            <StatusBadge status={ticket.status} />
            <span className="text-[9.5px] font-medium text-slate-400">Original ticket data</span>
          </div>
        </div>
      </div>
    </button>
  );
}
