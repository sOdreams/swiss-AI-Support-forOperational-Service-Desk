import type { Priority } from "../types/ticket";

export function PriorityBadge({ priority }: { priority: Priority | null }) {
  if (!priority) {
    return <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-semibold text-slate-500">Not recorded</span>;
  }
  const critical = priority === "Highest";
  const high = priority === "High";
  return (
    <span className={`rounded border px-2 py-0.5 text-[10px] font-semibold ${
      critical
        ? "border-red-200 bg-red-50 text-red-700"
        : high
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-blue-200 bg-blue-50 text-blue-700"
    }`}>
      {priority}
    </span>
  );
}
