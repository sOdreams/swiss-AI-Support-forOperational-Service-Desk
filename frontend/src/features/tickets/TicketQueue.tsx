import { ChevronLeft, ChevronRight, Inbox, Search, SlidersHorizontal } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import type { Ticket } from "../../types/ticket";
import { TicketUpload, type UploadState } from "../upload/TicketUpload";
import { TicketListItem } from "./TicketListItem";

const PAGE_SIZE = 50;

type SortMode = "priority" | "newest" | "oldest";

function priorityRank(priority: string | null) {
  const value = (priority ?? "").toLowerCase();
  if (["p1", "highest", "critical", "urgent"].includes(value)) return 0;
  if (["p2", "high"].includes(value)) return 1;
  if (["p3", "medium"].includes(value)) return 2;
  if (["p4", "low"].includes(value)) return 3;
  if (["p5", "lowest"].includes(value)) return 4;
  return 5;
}

function timeValue(value: string) {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function TicketQueue({
  tickets,
  selectedTicketId,
  onSelectTicket,
  onTicketsLoaded,
  onUploadError,
  uploadState,
}: {
  tickets: Ticket[];
  selectedTicketId?: string;
  onSelectTicket: (ticket: Ticket) => void;
  onTicketsLoaded: (tickets: Ticket[], fileName: string) => void;
  onUploadError: (fileName: string, message: string) => void;
  uploadState: UploadState;
}) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [sortMode, setSortMode] = useState<SortMode>("priority");
  const [page, setPage] = useState(1);

  const statuses = useMemo(
    () => [...new Set(tickets.map((ticket) => ticket.status).filter(Boolean))].sort(),
    [tickets],
  );

  const priorities = useMemo(
    () => [...new Set(tickets.map((ticket) => ticket.priority).filter((value): value is NonNullable<Ticket["priority"]> => Boolean(value)))],
    [tickets],
  );

  const filtered = useMemo(() => {
    const q = deferredQuery.trim().toLowerCase();
    const result = tickets.filter((ticket) => {
      const searchable = [
        ticket.issue_key,
        ticket.summary,
        ticket.priority ?? "",
        ticket.status,
        ticket.business_entity ?? "",
        ...ticket.service_teams,
      ]
        .join(" ")
        .toLowerCase();
      const matchesQuery = !q || searchable.includes(q);
      const matchesStatus = status === "all" || ticket.status === status;
      const matchesPriority = priority === "all" || ticket.priority === priority;
      return matchesQuery && matchesStatus && matchesPriority;
    });

    return result.sort((a, b) => {
      if (sortMode === "newest") return timeValue(b.created_date) - timeValue(a.created_date);
      if (sortMode === "oldest") return timeValue(a.created_date) - timeValue(b.created_date);
      const byPriority = priorityRank(a.priority) - priorityRank(b.priority);
      return byPriority !== 0 ? byPriority : timeValue(b.created_date) - timeValue(a.created_date);
    });
  }, [tickets, deferredQuery, status, priority, sortMode]);

  const criticalCount = useMemo(
    () => tickets.filter((ticket) => priorityRank(ticket.priority) === 0).length,
    [tickets],
  );
  const unassignedCount = useMemo(() => tickets.filter((ticket) => !ticket.assignee).length, [tickets]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const start = (safePage - 1) * PAGE_SIZE;
  const visibleTickets = filtered.slice(start, start + PAGE_SIZE);

  useEffect(() => {
    setPage(1);
  }, [deferredQuery, status, priority, sortMode, tickets]);

  return (
    <aside className="panel-left min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-left">
        <div className="flex items-center gap-3">
          <span className="section-step section-step-left">01</span>
          <span className="section-icon section-icon-left"><Inbox className="h-4 w-4" /></span>
          <div>
            <h2 className="section-title">Ticket Queue</h2>
            <p className="section-subtitle">Find the next case that needs attention</p>
          </div>
        </div>
        {tickets.length > 0 ? (
          <div className="queue-total" title="Total tickets loaded">
            <span className="queue-total-number">{tickets.length.toLocaleString()}</span>
            <span className="queue-total-label">loaded</span>
          </div>
        ) : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-auto">
        <div className="min-w-[410px]">
          <div className="queue-controls sticky top-0 z-10 space-y-3 border-b border-[#E4D8CC] p-4">
            <TicketUpload onLoaded={onTicketsLoaded} onError={onUploadError} state={uploadState} />

            {tickets.length > 0 ? (
              <>
                <label className="relative block">
                  <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#9A7755]" />
                  <input
                    value={query}
                    onChange={(event: { target: { value: string } }) => setQuery(event.target.value)}
                    placeholder="Search key, summary, team, entity..."
                    className="w-full rounded-xl border border-[#E3D7CB] bg-white/95 py-2.5 pl-8 pr-3 text-[12px] text-slate-700 shadow-sm outline-none transition focus:border-[#B99470] focus:ring-2 focus:ring-[#EFE4D8]"
                  />
                </label>

                <div className="grid grid-cols-3 gap-2">
                  <select
                    value={priority}
                    onChange={(event: { target: { value: string } }) => setPriority(event.target.value)}
                    className="queue-select"
                  >
                    <option value="all">All priorities</option>
                    {priorities.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                  <select
                    value={status}
                    onChange={(event: { target: { value: string } }) => setStatus(event.target.value)}
                    className="queue-select"
                  >
                    <option value="all">All statuses</option>
                    {statuses.map((value) => <option key={value} value={value}>{value}</option>)}
                  </select>
                  <label className="relative">
                    <SlidersHorizontal className="pointer-events-none absolute left-2.5 top-2.5 h-3.5 w-3.5 text-[#A17A55]" />
                    <select
                      value={sortMode}
                      onChange={(event: { target: { value: string } }) => setSortMode(event.target.value as SortMode)}
                      className="queue-select w-full pl-8"
                    >
                      <option value="priority">Priority first</option>
                      <option value="newest">Newest first</option>
                      <option value="oldest">Oldest first</option>
                    </select>
                  </label>
                </div>

                <div className="queue-health-grid">
                  <div><strong>{filtered.length.toLocaleString()}</strong><span>matching</span></div>
                  <div><strong>{criticalCount.toLocaleString()}</strong><span>critical</span></div>
                  <div><strong>{unassignedCount.toLocaleString()}</strong><span>unassigned</span></div>
                </div>

                <div className="flex items-center justify-between gap-3 text-[11px]">
                  <span className="font-semibold text-[#8A6C51]">Only 50 tickets render per page</span>
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
              <p className="mt-3 text-[13px] font-bold text-slate-800">Upload a JSON file to load tickets</p>
              <p className="mx-auto mt-1 max-w-[280px] text-[11px] leading-4 text-slate-500">Built for large queues: search, filter and paginate without rendering thousands of cards at once.</p>
            </div>
          ) : (
            <>
              <div className="pb-2 pt-3">
                {visibleTickets.map((ticket) => (
                  <TicketListItem
                    key={ticket.issue_id}
                    ticket={ticket}
                    selected={ticket.issue_id === selectedTicketId}
                    onSelect={onSelectTicket}
                  />
                ))}
                {filtered.length === 0 ? (
                  <div className="p-8 text-center text-[12px] text-slate-400">No tickets match the current filters.</div>
                ) : null}
              </div>

              {filtered.length > PAGE_SIZE ? (
                <div className="queue-pagination sticky bottom-0 z-10 mx-3 mb-3 flex items-center justify-between rounded-2xl border border-[#E4D8CC] bg-white/95 px-3 py-2.5 shadow-[0_-8px_24px_rgba(72,54,37,0.07)] backdrop-blur">
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={safePage === 1}
                    className="queue-page-button"
                  >
                    <ChevronLeft className="h-3.5 w-3.5" /> Prev
                  </button>
                  <span className="text-[11px] font-semibold text-slate-500">
                    Page <strong className="text-slate-800">{safePage}</strong> of {pageCount.toLocaleString()}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                    disabled={safePage === pageCount}
                    className="queue-page-button"
                  >
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
