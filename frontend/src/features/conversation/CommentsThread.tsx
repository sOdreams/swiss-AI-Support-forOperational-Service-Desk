import { LockKeyhole, MessageSquareText, Wrench } from "lucide-react";
import { formatDate } from "../../lib/utils";
import type { JiraComment } from "../../types/ticket";

export function CommentsThread({ comments }: { comments: JiraComment[] }) {
  if (comments.length === 0) return <div className="p-6 text-center text-xs text-slate-400">No comments recorded.</div>;
  return (
    <div className="space-y-4 p-5">
      {comments.map((comment) => (
        <article key={comment.id} className={`rounded-lg border p-3.5 ${comment.visibility === "internal" ? "border-blue-100 bg-blue-50/50" : "border-slate-200 bg-white"}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-500">
                {comment.semantic_role === "action" ? <Wrench className="h-3.5 w-3.5" /> : <MessageSquareText className="h-3.5 w-3.5" />}
              </div>
              <div>
                <p className="text-[10px] font-semibold text-slate-800">{comment.author.display_name}</p>
                <p className="text-[9px] text-slate-400">{formatDate(comment.created_at)}</p>
              </div>
            </div>
            <div className="flex gap-1.5">
              {comment.visibility === "internal" ? <span className="inline-flex items-center gap-1 rounded border border-blue-200 bg-white px-1.5 py-0.5 text-[8px] font-semibold text-blue-700"><LockKeyhole className="h-2.5 w-2.5" />Internal note</span> : <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[8px] font-semibold text-slate-500">Requester-visible</span>}
              {comment.semantic_role === "action" ? <span className="rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[8px] font-semibold text-amber-700">Action</span> : null}
              {comment.semantic_role === "result" ? <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[8px] font-semibold text-slate-600">Observed result</span> : null}
            </div>
          </div>
          <p className="mt-3 text-[11px] leading-5 text-slate-700">{comment.body}</p>
        </article>
      ))}
    </div>
  );
}
