interface StatusBadgeProps {
  status?: string;
}

const statusStyles: Record<string, string> = {
  new: "border-blue-200 bg-blue-50 text-blue-700",
  in_progress: "border-amber-200 bg-amber-50 text-amber-800",
  resolved: "border-emerald-200 bg-emerald-50 text-emerald-700",
  closed: "border-slate-200 bg-slate-100 text-slate-600",
};

function labelForStatus(status: string): string {
  return status.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function StatusBadge({ status = "unknown" }: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  const styles = statusStyles[normalized] ?? "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${styles}`}
    >
      {labelForStatus(normalized)}
    </span>
  );
}
