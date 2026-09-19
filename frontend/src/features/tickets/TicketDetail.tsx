import type { ReactNode } from "react";
import { Building2, CalendarClock, Link2, MessageSquareText, UserRound } from "lucide-react";
import { NullableValue } from "../../components/NullableValue";
import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { displayBoolean, formatDate } from "../../lib/utils";
import type { Ticket } from "../../types/ticket";
import { CommentsThread } from "../conversation/CommentsThread";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div><p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-400">{label}</p><div className="mt-1 text-[11px] font-medium text-slate-700">{children}</div></div>;
}

export function TicketDetail({ ticket }: { ticket?: Ticket }) {
  if (!ticket) return <main className="flex min-w-0 flex-1 items-center justify-center bg-white text-sm text-slate-400">Select a ticket.</main>;
  return (
    <main className="flex min-w-0 flex-1 flex-col bg-white">
      <div className="shrink-0 border-b border-[#DCE3EC] px-6 py-4">
        <div className="mb-2 flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-blue-700"><span className="rounded bg-blue-50 px-2 py-1">Original Jira data</span><span className="text-slate-400">Source of truth</span></div>
        <div className="flex items-start justify-between gap-5">
          <div className="min-w-0">
            <div className="flex items-center gap-2"><span className="font-mono text-xs font-bold text-slate-500">{ticket.issue_key}</span><StatusBadge status={ticket.status} /><PriorityBadge priority={ticket.priority} /></div>
            <h1 className="mt-2 text-xl font-bold tracking-tight text-slate-950">{ticket.summary}</h1>
            <p className="mt-2 max-w-3xl text-[12px] leading-5 text-slate-600"><NullableValue value={ticket.description} /></p>
          </div>
          <div className="min-w-[170px] rounded-lg border border-slate-200 bg-slate-50 p-3">
            <p className="text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-400">Assignee</p>
            <p className="mt-1 text-[11px] font-semibold text-slate-800">{ticket.assignee?.display_name ?? "Unassigned"}</p>
            <p className="mt-2 text-[9px] text-slate-400">Service team</p>
            <p className="mt-0.5 text-[10px] text-slate-600">{ticket.service_teams.join(", ") || "Not recorded"}</p>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-5 gap-4 border-t border-slate-100 pt-4">
          <Field label="Reporter"><span className="inline-flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5 text-slate-400" />{ticket.reporter?.display_name ?? "Not recorded"}</span></Field>
          <Field label="Business entity"><span className="inline-flex items-center gap-1.5"><Building2 className="h-3.5 w-3.5 text-slate-400" /><NullableValue value={ticket.business_entity} /></span></Field>
          <Field label="Work type"><NullableValue value={ticket.work_type} /></Field>
          <Field label="Request type"><NullableValue value={ticket.request_type} /></Field>
          <Field label="Created"><span className="inline-flex items-center gap-1.5"><CalendarClock className="h-3.5 w-3.5 text-slate-400" />{formatDate(ticket.created_date)}</span></Field>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 grid-rows-[auto_1fr]">
        <div className="border-b border-[#DCE3EC] bg-slate-50/60 px-6 py-3">
          <div className="grid grid-cols-2 gap-4">
            <section className="rounded-lg border border-slate-200 bg-white p-3.5">
              <p className="text-[10px] font-bold text-slate-800">Workflow state</p>
              <div className="mt-3 grid grid-cols-2 gap-4">
                <Field label="Status"><StatusBadge status={ticket.status} /></Field>
                <Field label="Resolution"><NullableValue value={ticket.resolution} /></Field>
              </div>
              <p className="mt-3 text-[9px] leading-4 text-slate-400">Status shows where the work is. Resolution shows how the case ended. They are intentionally separate.</p>
            </section>
            <section className="rounded-lg border border-slate-200 bg-white p-3.5">
              <p className="text-[10px] font-bold text-slate-800">Recorded operational data</p>
              <div className="mt-3 grid grid-cols-3 gap-3">
                <Field label="Urgency"><NullableValue value={ticket.urgency} /></Field>
                <Field label="Impact"><NullableValue value={ticket.impact} /></Field>
                <Field label="Severity"><NullableValue value={ticket.severity} /></Field>
                <Field label="Due date">{formatDate(ticket.due_date)}</Field>
                <Field label="Business critical">{displayBoolean(ticket.business_critical_for_entity)}</Field>
                <Field label="Affected services">{ticket.affected_business_or_it_services.join(", ") || "None recorded"}</Field>
              </div>
            </section>
          </div>

          <details className="mt-3 rounded-lg border border-slate-200 bg-white">
            <summary className="cursor-pointer px-4 py-3 text-[10px] font-semibold text-blue-700">View all original Jira fields and linked issues</summary>
            <div className="grid grid-cols-4 gap-4 border-t border-slate-100 px-4 py-4">
              <Field label="Issue ID">{ticket.issue_id}</Field><Field label="Issue Key">{ticket.issue_key}</Field><Field label="Priority"><NullableValue value={ticket.priority} /></Field><Field label="Due date">{formatDate(ticket.due_date)}</Field>
              <Field label="Work type"><NullableValue value={ticket.work_type} /></Field><Field label="Request type"><NullableValue value={ticket.request_type} /></Field><Field label="Urgency"><NullableValue value={ticket.urgency} /></Field><Field label="Impact"><NullableValue value={ticket.impact} /></Field>
              <Field label="Severity"><NullableValue value={ticket.severity} /></Field><Field label="Business entity"><NullableValue value={ticket.business_entity} /></Field><Field label="Business critical">{displayBoolean(ticket.business_critical_for_entity)}</Field><Field label="Service teams">{ticket.service_teams.join(", ") || "None recorded"}</Field>
            </div>
            <div className="border-t border-slate-100 px-4 py-4">
              <div className="flex items-center gap-2"><Link2 className="h-3.5 w-3.5 text-slate-400" /><p className="text-[10px] font-bold text-slate-800">Linked issues</p></div>
              {ticket.linked_issues.length ? <div className="mt-2 space-y-2">{ticket.linked_issues.map((issue) => <div key={`${issue.relation}-${issue.issue_key}`} className="flex items-center gap-2 rounded-md bg-slate-50 px-3 py-2 text-[10px]"><span className="font-semibold text-slate-500">{issue.relation}</span><span className="font-mono font-bold text-blue-700">{issue.issue_key}</span><span className="min-w-0 flex-1 truncate text-slate-700">{issue.summary}</span><span className="text-slate-400">{issue.status ?? "Status not recorded"}</span></div>)}</div> : <p className="mt-2 text-[10px] italic text-slate-400">No linked issues recorded.</p>}
            </div>
          </details>
        </div>

        <section className="min-h-0 overflow-y-auto">
          <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#DCE3EC] bg-white/95 px-6 py-3 backdrop-blur">
            <div className="flex items-center gap-2"><MessageSquareText className="h-4 w-4 text-blue-700" /><h2 className="text-xs font-bold text-slate-900">All Comments</h2><span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] text-slate-500">{ticket.all_comments.length}</span></div>
            <p className="text-[9px] text-slate-400">Each entry is one comment in the ticket conversation</p>
          </div>
          <CommentsThread comments={ticket.all_comments} />
        </section>
      </div>
    </main>
  );
}
