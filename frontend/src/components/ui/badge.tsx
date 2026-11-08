import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  connected: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  active: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  PUBLISHED: "bg-emerald-50 text-emerald-900 ring-emerald-200",
  PENDING_APPROVAL: "bg-amber-50 text-amber-950 ring-amber-200",
  SCHEDULED: "bg-slate-50 text-slate-800 ring-slate-200",
  GENERATING: "bg-slate-50 text-slate-800 ring-slate-200",
  PUBLISHING: "bg-slate-50 text-slate-800 ring-slate-200",
  paused: "bg-canvas text-muted ring-line",
  FAILED: "bg-red-50 text-red-900 ring-red-200",
  needs_reauth: "bg-red-50 text-red-900 ring-red-200",
  UNKNOWN: "bg-orange-50 text-orange-950 ring-orange-200",
  CANCELLED: "bg-canvas text-muted ring-line",
  archived: "bg-canvas text-muted ring-line",
};

export function Badge({ value, label }: { value: string; label: string }) {
  return (
    <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ring-1 ring-inset", tones[value] ?? "bg-canvas text-muted ring-line")}>
      {label}
    </span>
  );
}
