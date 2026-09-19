import { Inbox, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { Ticket } from "../../types/ticket";
import { TicketListItem } from "./TicketListItem";

export function TicketQueue({ tickets, selectedTicketId, onSelectTicket }: { tickets: Ticket[]; selectedTicketId?: string; onSelectTicket: (ticket: Ticket) => void }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const filtered = useMemo(() => tickets.filter((ticket) => {
    const q = query.trim().toLowerCase();
    const matchesQuery = !q || [ticket.issue_key, ticket.summary, ...ticket.service_teams].some((v) => v.toLowerCase().includes(q));
    const matchesStatus = status === "all" || ticket.status === status;
    return matchesQuery && matchesStatus;
  }), [tickets, query, status]);

  return (
    <aside className="flex min-h-0 w-[270px] shrink-0 flex-col border-r border-[#DCE3EC] bg-[#F7F9FC]">
      <div className="border-b border-[#DCE3EC] bg-[#F1F5F9] px-4 py-4">
        <div className="flex items-center gap-2"><Inbox className="h-4 w-4 text-blue-700" /><h2 className="text-xs font-bold text-slate-900">Ticket Queue</h2></div>
        <p className="mt-1 text-[10px] text-slate-500">Original Jira tickets · select one to review</p>
      </div>
      <div className="space-y-2 border-b border-[#DCE3EC] p-3">
        <label className="relative block">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input value={query} onChange={(e: { target: { value: string } }) => setQuery(e.target.value)} placeholder="Search key, summary or team" className="w-full rounded-md border border-slate-200 bg-white py-2 pl-8 pr-2 text-[10px] outline-none focus:border-blue-300" />
        </label>
        <select value={status} onChange={(e: { target: { value: string } }) => setStatus(e.target.value)} className="w-full rounded-md border border-slate-200 bg-white px-2 py-2 text-[10px] text-slate-600">
          <option value="all">All statuses</option>
          {[...new Set(tickets.map((t) => t.status))].map((value) => <option key={value} value={value}>{value}</option>)}
        </select>
      </div>
      <div className="flex items-center justify-between border-b border-[#DCE3EC] bg-[#F1F5F9] px-3.5 py-2"><span className="text-[10px] text-slate-500">Tickets</span><span className="text-[10px] text-slate-400">{filtered.length}</span></div>
      <div className="min-h-0 flex-1 overflow-y-auto">{filtered.map((ticket) => <TicketListItem key={ticket.issue_id} ticket={ticket} selected={ticket.issue_id === selectedTicketId} onSelect={onSelectTicket} />)}</div>
    </aside>
  );
}
