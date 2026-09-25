import { ChevronLeft, ChevronRight, Inbox, Search, SlidersHorizontal } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import type { Ticket } from "../../types/ticket";
import type { TicketAnalysisStatus } from "../../types/triage";
import { TicketUpload, type UploadState } from "../upload/TicketUpload";
import { TicketListItem } from "./TicketListItem";

const PAGE_SIZE = 50;
type SortMode = "newest" | "oldest" | "uploaded";

function timeValue(value: string) {
  const parsed = Date.parse(value.replace(" ", "T"));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function TicketQueue({
  tickets,
  onTicketsLoaded,
  onUploadError,
  uploadState,
  onFilteredTicketsChange,
  selectedTicketId,
  onSelectTicket,
  analysisStatuses,
}: {
  tickets: Ticket[];
  onTicketsLoaded: (tickets: Ticket[], fileName: string) => void;
  onUploadError: (fileName: string, message: string) => void;
  uploadState: UploadState;
  onFilteredTicketsChange: (tickets: Ticket[]) => void;
  selectedTicketId: string | null;
  onSelectTicket: (ticket: Ticket) => void;
  analysisStatuses: Record<string, TicketAnalysisStatus>;
}) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [status, setStatus] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [page, setPage] = useState(1);

  const statuses = useMemo(
    () => [...new Set(tickets.map((ticket) => ticket.status).filter(Boolean))].sort(),
    [tickets],
  );

  const filtered = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();
    const withIndex = tickets.map((ticket, index) => ({ ticket, index }));

    const result = withIndex.filter(({ ticket }) => {
      const searchable = [
        ticket.summary,
        ticket.description ?? "",
        ticket.work_type ?? "",
        ticket.request_type ?? "",
        ticket.status,
        ticket.business_entity ?? "",
        ticket.reporter?.display_name ?? "",
        ...ticket.affected_business_or_it_services,
      ]
        .join(" ")
        .toLowerCase();

      return (!q || searchable.includes(q)) && (status === "all" || ticket.status === status);
    });

    result.sort((a, b) => {
      if (sortMode === "uploaded") return a.index - b.index;
      if (sortMode === "oldest") return timeValue(a.ticket.created_date) - timeValue(b.ticket.created_date);
      return timeValue(b.ticket.created_date) - timeValue(a.ticket.created_date);
    });

    return result.map(({ ticket }) => ticket);
  }, [tickets, deferredQuery, status, sortMode]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const start = (safePage - 1) * PAGE_SIZE;
  const visibleTickets = filtered.slice(start, start + PAGE_SIZE);

  useEffect(() => setPage(1), [deferredQuery, status, sortMode, tickets]);
  useEffect(() => onFilteredTicketsChange(filtered), [filtered, onFilteredTicketsChange]);

  return (
    <aside className="panel-left min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-left">
        <div className="flex items-center gap-3">
          <span className="section-step section-step-left">01</span>
          <span className="section-icon section-icon-left"><Inbox className="h-4 w-4" /></span>
          <div>
            <h2 className="section-title">Incoming Tickets</h2>
            <p className="section-subtitle">Original ticket data · no AI priority shown here</p>
          </div>
        </div>
        {tickets.length > 0 ? (
          <div className="queue-total" title="Tickets loaded from the source JSON">
            <span className="queue-total-number">{tickets.length.toLocaleString()}</span>
            <span className="queue-total-label">loaded</span>
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain">
        <div className="w-full min-w-0">
          <div className="queue-controls sticky top-0 z-10 space-y-3 border-b border-[#E4D8CC] p-4">
            <TicketUpload onLoaded={onTicketsLoaded} onError={onUploadError} state={uploadState} />

            {tickets.length > 0 ? (
              <>
                <label className="relative block">
                  <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#9A7755]" />
                  <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search summary, service, entity, reporter..."
                    className="w-full rounded-xl border border-[#E3D7CB] bg-white/95 py-2.5 pl-8 pr-3 text-[12px] text-slate-700 shadow-sm outline-none transition focus:border-[#B99470] focus:ring-2 focus:ring-[#EFE4D8]"
                  />
                </label>

                <div className="grid grid-cols-2 gap-2">
                  <select value={status} onChange={(event) => setStatus(event.target.value)} className="queue-select">
                    <option value="all">All statuses</option>
                    {statuses.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>

                  <label className="relative">
                    <SlidersHorizontal className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[#A17A55]" />
                    <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} className="queue-select w-full pl-8">
                      <option value="newest">Newest first</option>
                      <option value="oldest">Oldest first</option>
                      <option value="uploaded">Upload order</option>
                    </select>
                  </label>
                </div>

                <div className="flex items-center justify-between gap-3 border-t border-[#E8DDD2] pt-2 text-[10px]">
                  <span className="font-semibold text-[#8A6C51]">Original input only</span>
                  <span className="text-slate-400">
                    {filtered.length ? start + 1 : 0}–{Math.min(start + PAGE_SIZE, filtered.length).toLocaleString()} of {filtered.length.toLocaleString()}
                  </span>
                </div>
              </>
            ) : null}
          </div>

          {tickets.length === 0 ? (
            <div className="m-4 rounded-2xl border border-dashed border-[#D7C5B4] bg-white/55 px-5 py-11 text-center shadow-sm">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#F0E5D9] text-[#9A7755]"><Inbox className="h-5 w-5" /></span>
              <p className="mt-3 text-[13px] font-bold text-slate-800">Upload the Swiss AI JSON</p>
              <p className="mx-auto mt-1 max-w-[280px] text-[11px] leading-4 text-slate-500">Supports the official wrapper format with a <code>records</code> array and plain ticket arrays.</p>
            </div>
          ) : (
            <>
              <div className="pb-2 pt-3">
                {visibleTickets.map((ticket) => (
                  <TicketListItem
                    key={ticket.issue_id}
                    ticket={ticket}
                    selected={ticket.issue_id === selectedTicketId}
                    onClick={() => onSelectTicket(ticket)}
                    analysisStatus={analysisStatuses[ticket.issue_id] ?? "idle"}
                  />
                ))}
                {filtered.length === 0 ? <div className="p-8 text-center text-[12px] text-slate-400">No tickets match the current filters.</div> : null}
              </div>

              {filtered.length > PAGE_SIZE ? (
                <div className="queue-pagination sticky bottom-0 z-10 mx-3 mb-3 flex items-center justify-between rounded-2xl border border-[#E4D8CC] bg-white/95 px-3 py-2.5 shadow-[0_-8px_24px_rgba(72,54,37,0.07)] backdrop-blur">
                  <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={safePage === 1} className="queue-page-button">
                    <ChevronLeft className="h-3.5 w-3.5" /> Prev
                  </button>
                  <span className="text-[11px] font-semibold text-slate-500">Page <strong className="text-slate-800">{safePage}</strong> of {pageCount.toLocaleString()}</span>
                  <button type="button" onClick={() => setPage((current) => Math.min(pageCount, current + 1))} disabled={safePage === pageCount} className="queue-page-button">
                    Next <ChevronRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </div>
    </aside>
  );
}
