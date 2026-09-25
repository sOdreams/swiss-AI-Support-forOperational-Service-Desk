import type { ReactNode } from "react";

export function TicketFieldGroup({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="interactive-card rounded-xl border border-slate-200/80 bg-white p-4 shadow-[0_1px_3px_rgba(15,23,42,0.035)]">
      <div className="mb-3 border-b border-slate-100 pb-2.5">
        <h3 className="text-[12px] font-bold uppercase tracking-[0.1em] text-[#4C6688]">{title}</h3>
        {description ? <p className="mt-1 text-[11px] leading-4 text-slate-400">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
