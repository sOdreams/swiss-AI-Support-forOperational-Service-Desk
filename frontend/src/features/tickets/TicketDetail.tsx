import { Building2, Clock3, Layers3, Sparkles, UserRound } from "lucide-react";
import { Button } from "../../components/ui/button";
import { StatusBadge } from "../../components/StatusBadge";
import { formatTicketDate } from "../../lib/utils";
import type { Ticket } from "../../types/ticket";

interface TicketDetailProps {
  ticket?: Ticket;
  onAnalyze: () => void;
}

interface DetailItemProps {
  label: string;
  value?: string;
  icon: typeof Building2;
}

function DetailItem({ label, value, icon: Icon }: DetailItemProps) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 rounded-md border border-slate-200 bg-slate-50 p-2 text-slate-500">
        <Icon aria-hidden="true" className="h-4 w-4" />
      </div>
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</dt>
        <dd className="mt-1 text-sm font-medium text-slate-800">{value || "Not provided"}</dd>
      </div>
    </div>
  );
}

export function TicketDetail({ ticket, onAnalyze }: TicketDetailProps) {
  if (!ticket) {
    return (
      <main className="flex flex-1 items-center justify-center bg-slate-50 p-8">
        <div className="max-w-sm text-center">
          <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm">
            <Layers3 aria-hidden="true" className="h-5 w-5 text-slate-500" />
          </div>
          <h2 className="mt-4 text-base font-semibold text-slate-900">Select a ticket to begin</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Choose a request from the queue to inspect the original Service Desk ticket.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-w-0 flex-1 overflow-y-auto bg-slate-50">
      <div className="mx-auto max-w-5xl p-8">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-sm font-bold tracking-wide text-slate-500">
                {ticket.id}
              </span>
              <StatusBadge status={ticket.status} />
            </div>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-950">
              {ticket.title}
            </h1>
          </div>

          <Button onClick={onAnalyze} aria-label={`Analyze ticket ${ticket.id}`}>
            <Sparkles aria-hidden="true" className="h-4 w-4" />
            Analyze Ticket
          </Button>
        </div>

        <section className="mt-7 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-6 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-slate-500">
              Original Request
            </p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900">Ticket Details</h2>
          </div>

          <div className="p-6">
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Description</h3>
              <p className="mt-2 max-w-3xl whitespace-pre-wrap text-sm leading-7 text-slate-700">
                {ticket.description}
              </p>
            </div>

            <dl className="mt-8 grid gap-6 border-t border-slate-200 pt-6 sm:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="Department" value={ticket.department} icon={Building2} />
              <DetailItem label="Service" value={ticket.service} icon={Layers3} />
              <DetailItem label="Requester" value={ticket.requester_id} icon={UserRound} />
              <DetailItem
                label="Created"
                value={formatTicketDate(ticket.created_at)}
                icon={Clock3}
              />
            </dl>
          </div>
        </section>

        <p className="mt-4 text-xs leading-5 text-slate-500">
          AI-assisted analysis is intentionally not implemented in this iteration. The original ticket remains the only decision input shown here.
        </p>
      </div>
    </main>
  );
}
