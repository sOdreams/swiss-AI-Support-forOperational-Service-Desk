import { CheckCircle2, CircleDot, Database } from "lucide-react";
import type { ProcessedTicketRecord } from "../../types/processing";

export function ProcessedTicketsPanel({ tickets }: { tickets: ProcessedTicketRecord[] }) {
  return (
    <aside className="panel-right min-h-0 min-w-0 overflow-hidden">
      <div className="panel-header panel-header-right">
        <div className="flex min-w-0 items-center gap-3">
          <span className="section-step section-step-right">03</span>
          <span className="section-icon section-icon-right"><CheckCircle2 className="h-4 w-4" /></span>
          <div className="min-w-0">
            <h2 className="section-title">Processed Tickets</h2>
            <p className="section-subtitle">Tickets completed by the analyst</p>
          </div>
        </div>
        {tickets.length > 0 ? <span className="processed-count">{tickets.length}</span> : null}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-contain p-3">
        {tickets.length === 0 ? (
          <div className="processed-empty">
            <CheckCircle2 className="mx-auto h-6 w-6 text-emerald-600" />
            <p>Processed tickets will appear here</p>
            <span>Complete a ticket in the middle panel and press Send.</span>
          </div>
        ) : (
          <div className="space-y-2.5">
            {tickets.map((ticket) => (
              <article key={`${ticket.issue_id}-${ticket.processed_at}`} className="processed-ticket-card">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-mono text-[10.5px] font-extrabold text-emerald-800">{ticket.issue_key}</p>
                    <h3 className="mt-1 line-clamp-2 text-[11px] font-extrabold leading-4 text-slate-800">{ticket.summary}</h3>
                  </div>
                  <span className={`processed-sync processed-sync-${ticket.sync_status}`} title={ticket.sync_status === "api" ? "Saved to backend" : "Saved locally"}>
                    {ticket.sync_status === "api" ? <Database className="h-3 w-3" /> : <CircleDot className="h-3 w-3" />}
                  </span>
                </div>

                <div className="mt-2.5 space-y-2 border-t border-emerald-100 pt-2.5">
                  <div>
                    <span className="processed-label">Solution</span>
                    <p className="processed-value line-clamp-3">{ticket.recommended_solution ?? ticket.real_solution ?? "—"}</p>
                  </div>
                  <div>
                    <span className="processed-label">Business aspect</span>
                    <p className="processed-value line-clamp-2">{ticket.affected_business_aspect}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
