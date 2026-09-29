export function NullableValue({ value, emptyLabel = "Not recorded" }: { value: string | null | undefined; emptyLabel?: string }) {
  if (value === null || value === undefined || value === "") {
    return <span className="italic text-slate-400">{emptyLabel}</span>;
  }
  return <>{value}</>;
}
