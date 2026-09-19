export function formatDate(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function relativeAge(value: string): string {
  const date = new Date(value).getTime();
  const diff = Math.max(0, Date.now() - date);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function displayNullable(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? "Not recorded" : value;
}

export function displayBoolean(value: boolean | null | undefined): string {
  if (value === null || value === undefined) return "Not recorded";
  return value ? "Yes" : "No";
}

export function confidenceLabel(value: number): "High" | "Medium" | "Low" {
  if (value >= 0.85) return "High";
  if (value >= 0.65) return "Medium";
  return "Low";
}
