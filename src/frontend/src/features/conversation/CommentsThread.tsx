import { LockKeyhole, MessageSquareText, Wrench } from "lucide-react";
import { formatDate } from "../../lib/utils";
import type { JiraComment } from "../../types/ticket";

export function CommentsThread({ comments }: { comments: JiraComment[] }) {
  if (comments.length === 0) return <div className="rounded-lg border border-dashed border-slate-200 bg-white/60 p-6 text-center text-[12px] text-slate-400">No comments recorded.</div>;
  return (
    <div className="space-y-3">
      {comments.map((comment) => (
        <article key={comment.id} className={`rounded-xl border p-3.5 ${comment.visibility === "internal" ? "border-[#DED4EA] bg-[#F8F5FB]" : "border-slate-200 bg-white"}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2.5">
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${comment.semantic_role === "action" ? "border-amber-200 bg-amber-50 text-amber-700" : "border-slate-200 bg-white text-slate-500"}`}>
                {comment.semantic_role === "action" ? <Wrench className="h-3.5 w-3.5" /> : <MessageSquareText className="h-3.5 w-3.5" />}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[12px] font-semibold text-slate-800">{comment.author.display_name}</p>
                <p className="text-[10px] text-slate-400">{comment.created_at ? formatDate(comment.created_at) : "Date not recorded"}</p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
              {comment.visibility === "internal" ? <span className="inline-flex items-center gap-1 rounded-md border border-[#D8CBE6] bg-white px-1.5 py-0.5 text-[10px] font-semibold text-[#7252A3]"><LockKeyhole className="h-2.5 w-2.5" />Internal</span> : null}
              {comment.semantic_role === "action" ? <span className="rounded-md border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700">Action</span> : null}
              {comment.semantic_role === "result" ? <span className="rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">Observed result</span> : null}
            </div>
          </div>
          <p className="mt-3 whitespace-pre-wrap text-[13px] leading-5 text-slate-700">{comment.body}</p>
        </article>
      ))}
    </div>
  );
}
