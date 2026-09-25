import { Braces } from "lucide-react";
import type { Ticket } from "../../types/ticket";

export function RawJsonViewer({ ticket }: { ticket: Ticket }) {
  const raw = ticket.raw ?? ticket;
  return (
    <details className="rounded-xl border border-[#DCE3EC] bg-[#172033] text-slate-100 shadow-sm">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-[12px] font-semibold text-slate-200 hover:bg-white/5">
        <Braces className="h-4 w-4 text-[#B7A4D4]" />
        View raw JSON
        <span className="ml-auto text-[10px] font-normal text-slate-500">Technical view</span>
      </summary>
      <div className="border-t border-white/10">
        <pre className="max-h-[360px] overflow-auto p-4 text-[11px] leading-4 text-slate-300">{JSON.stringify(raw, null, 2)}</pre>
      </div>
    </details>
  );
}
