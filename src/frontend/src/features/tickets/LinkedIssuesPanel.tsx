import { ExternalLink, Link2 } from "lucide-react";
import type { LinkedIssue } from "../../types/ticket";

export function LinkedIssuesPanel({ issues }: { issues: LinkedIssue[] }) {
  if (issues.length === 0) return <p className="text-[12px] italic text-slate-400">No linked issues recorded.</p>;
  return (
    <div className="space-y-2">
      {issues.map((issue) => (
        <div key={`${issue.relation}-${issue.issue_key}`} className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3 transition hover:border-[#C7D2DF] hover:shadow-sm">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#EEF2F6] text-[#4C6688]"><Link2 className="h-3.5 w-3.5" /></span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">{issue.relation}</span>
              <span className="font-mono text-[11px] font-bold text-[#4C6688]">{issue.issue_key}</span>
              {issue.status ? <span className="text-[10px] text-slate-400">· {issue.status}</span> : null}
            </div>
            <p className="mt-1 text-[12px] leading-4 text-slate-700">{issue.summary}</p>
          </div>
          <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-slate-300" />
        </div>
      ))}
    </div>
  );
}
