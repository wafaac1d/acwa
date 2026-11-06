import { cn } from "@/lib/utils";

const tones: Record<string, string> = {
  connected: "bg-emerald-100 text-emerald-900",
  active: "bg-emerald-100 text-emerald-900",
  PUBLISHED: "bg-emerald-100 text-emerald-900",
  PENDING_APPROVAL: "bg-amber-100 text-amber-950",
  SCHEDULED: "bg-sky-100 text-sky-950",
  GENERATING: "bg-sky-100 text-sky-950",
  PUBLISHING: "bg-sky-100 text-sky-950",
  paused: "bg-stone-200 text-stone-800",
  FAILED: "bg-red-100 text-red-900",
  needs_reauth: "bg-red-100 text-red-900",
  UNKNOWN: "bg-orange-100 text-orange-950",
  CANCELLED: "bg-stone-200 text-stone-700",
  archived: "bg-stone-200 text-stone-700",
};

export function Badge({ value, label }: { value: string; label: string }) {
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-semibold", tones[value] ?? "bg-stone-100")}>
      {label}
    </span>
  );
}
