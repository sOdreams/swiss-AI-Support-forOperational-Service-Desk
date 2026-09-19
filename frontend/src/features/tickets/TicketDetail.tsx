import type { ReactNode } from "react";
import { CalendarClock, CircleDot, FileText, Link2, MessageSquareText, UserRound } from "lucide-react";
import { NullableValue } from "../../components/NullableValue";
import { PriorityBadge } from "../../components/PriorityBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { displayBoolean, formatDate } from "../../lib/utils";
import type { Ticket } from "../../types/ticket";
import { CommentsThread } from "../conversation/CommentsThread";
import { LinkedIssuesPanel } from "./LinkedIssuesPanel";
import { RawJsonViewer } from "./RawJsonViewer";

function Field({ label, children, wide = false }: { label: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <p className="text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400">{label}</p>
      <div className="mt-1.5 text-[13px] font-medium leading-5 text-slate-700">{children}</div>
    </div>
  );
}

function ListValue({ values }: { values: string[] }) {
  if (values.length === 0) return <span className="italic text-slate-400">Not recorded</span>;
  return <span>{values.join(", ")}</span>;
}

function DataSection({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="border-t border-slate-200/80 pt-5 first:border-t-0 first:pt-0">
      <div className="mb-4">
        <h3 className="text-[13px] font-extrabold text-slate-900">{title}</h3>
        {description ? <p className="mt-1 text-[11px] leading-5 text-slate-500">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}

export function TicketDetail({ ticket }: { ticket?: Ticket }) {
  if (!ticket) {
    return (
      <main className="panel-center min-h-0 min-w-0 overflow-hidden">
        <div className="panel-header panel-header-center">
          <div className="flex items-center gap-2.5">
            <span className="section-step section-step-center">02</span>
            <span className="section-icon section-icon-center"><FileText className="h-4 w-4" /></span>
            <div>
              <h2 className="section-title">Ticket Detail</h2>
              <p className="section-subtitle">Original ticket information</p>
            </div>
          </div>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center overflow-y-auto overflow-x-hidden p-6">
          <div className="max-w-sm text-center">
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[#DBEAFE] text-[#315F9E]"><FileText className="h-5 w-5" /></span>
            <p className="mt-3 text-[14px] font-extrabold text-slate-900">Select a ticket to inspect the original data</p>
            <p className="mt-1.5 text-[11px] leading-5 text-slate-500">The middle workspace shows the Jira data exactly as imported from JSON.</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="panel-center min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-center">
        <div className="flex items-center gap-3">
          <span className="section-step section-step-center">02</span>
          <span className="section-icon section-icon-center"><FileText className="h-4 w-4" /></span>
          <div>
            <h2 className="section-title">Ticket Detail</h2>
            <p className="section-subtitle">Inspect the original Jira data</p>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain">
        <div className="w-full min-w-0 space-y-4 p-4 lg:p-5">
          <section className="rounded-2xl border border-[#C9D8EA] bg-gradient-to-br from-white to-[#F7FAFF] p-4 shadow-[0_10px_28px_rgba(49,95,158,0.08)]">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="rounded-md bg-[#EAF2FF] px-2.5 py-1 font-mono text-[12px] font-extrabold text-[#315F9E]">{ticket.issue_key}</span>
              <StatusBadge status={ticket.status} />
              <PriorityBadge priority={ticket.priority} />
            </div>
            <h1 className="mt-3 text-[20px] font-extrabold tracking-tight text-slate-950">{ticket.summary}</h1>
            <p className="mt-2 text-[9px] font-semibold uppercase tracking-[0.08em] text-slate-400">Original description</p>
            <p className="mt-1.5 max-w-4xl whitespace-pre-wrap text-[12px] leading-5.5 text-slate-700"><NullableValue value={ticket.description} /></p>
          </section>

          <section className="ticket-category-card">
            <div className="ticket-category-heading">
              <div>
                <p className="ticket-category-eyebrow">Ticket Category</p>
                <h2>How this ticket is currently classified</h2>
              </div>
              <span>Original Jira values</span>
            </div>
            <div className="ticket-category-grid">
              <Field label="Work type"><NullableValue value={ticket.work_type} /></Field>
              <Field label="Request type"><NullableValue value={ticket.request_type} /></Field>
              <Field label="Priority"><PriorityBadge priority={ticket.priority} /></Field>
              <Field label="Status"><span className="inline-flex items-center gap-1.5"><CircleDot className="h-3.5 w-3.5 text-[#315F9E]" />{ticket.status}</span></Field>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_5px_18px_rgba(15,23,42,0.045)]">
            <div className="mb-4 flex items-center justify-between gap-4 border-b border-slate-100 pb-3">
              <div>
                <h2 className="text-[14px] font-extrabold text-slate-900">Recorded ticket data</h2>
                <p className="mt-1 text-[10px] text-slate-500">Missing fields stay missing — they are never interpreted as low, false or resolved.</p>
              </div>
              <span className="rounded-full bg-[#EFF6FF] px-2.5 py-1 text-[9px] font-bold text-[#315F9E]">Source data</span>
            </div>

            <div className="space-y-5">
              <DataSection title="Workflow state" description="Status describes where the work is. Resolution describes how it ended.">
                <div className="detail-field-grid">
                  <Field label="Status"><span className="inline-flex items-center gap-1.5"><CircleDot className="h-3.5 w-3.5 text-[#315F9E]" />{ticket.status}</span></Field>
                  <Field label="Resolution"><NullableValue value={ticket.resolution} /></Field>
                </div>
              </DataSection>

              <DataSection title="Business & ownership">
                <div className="detail-field-grid">
                  <Field label="Affected services" wide><ListValue values={ticket.affected_business_or_it_services} /></Field>
                  <Field label="Business entity"><NullableValue value={ticket.business_entity} /></Field>
                  <Field label="Business critical">{displayBoolean(ticket.business_critical_for_entity)}</Field>
                  <Field label="Service Team(s)" wide><ListValue values={ticket.service_teams} /></Field>
                  <Field label="Reporter"><span className="inline-flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5 text-slate-400" />{ticket.reporter?.display_name ?? <span className="italic text-slate-400">Not recorded</span>}</span></Field>
                  <Field label="Assignee"><span className="inline-flex items-center gap-1.5"><UserRound className="h-3.5 w-3.5 text-slate-400" />{ticket.assignee?.display_name ?? <span className="italic text-slate-400">Not recorded</span>}</span></Field>
                </div>
              </DataSection>

              <DataSection title="Severity & dates">
                <div className="detail-field-grid">
                  <Field label="Urgency"><NullableValue value={ticket.urgency} /></Field>
                  <Field label="Impact"><NullableValue value={ticket.impact} /></Field>
                  <Field label="Severity"><NullableValue value={ticket.severity} /></Field>
                  <Field label="Created date"><span className="inline-flex items-center gap-1.5"><CalendarClock className="h-3.5 w-3.5 text-slate-400" />{formatDate(ticket.created_date)}</span></Field>
                  <Field label="Due date"><NullableValue value={ticket.due_date ? formatDate(ticket.due_date) : null} /></Field>
                  <Field label="Issue ID"><span className="break-all">{ticket.issue_id}</span></Field>
                </div>
              </DataSection>
            </div>
          </section>

          <section className="grid grid-cols-1 gap-4 2xl:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-[14px] font-extrabold text-slate-900">Linked issues</h3>
                  <p className="mt-1 text-[11px] text-slate-500">Readable relationships instead of raw JSON.</p>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600"><Link2 className="h-3.5 w-3.5" />{ticket.linked_issues.length}</span>
              </div>
              <LinkedIssuesPanel issues={ticket.linked_issues} />
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-[14px] font-extrabold text-slate-900">All Comments</h3>
                  <p className="mt-1 text-[11px] text-slate-500">Actions, results and collaboration remain separate entries.</p>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600"><MessageSquareText className="h-3.5 w-3.5" />{ticket.all_comments.length}</span>
              </div>
              <div className="max-h-[430px] overflow-y-auto pr-1"><CommentsThread comments={ticket.all_comments} /></div>
            </div>
          </section>

          <RawJsonViewer ticket={ticket} />
        </div>
      </div>
    </main>
  );
}
