export function StatusBadge({ status }: { status: string }) {
  const resolved = /resolved|closed/i.test(status);
  return (
    <span className={`rounded border px-2 py-0.5 text-[10px] font-semibold ${resolved ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-white text-slate-600"}`}>
      {status}
    </span>
  );
}
