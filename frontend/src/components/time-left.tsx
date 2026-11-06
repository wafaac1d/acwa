import { useEffect, useState } from "react";
import { timeLeftLabel } from "@/lib/time-left";

export function TimeLeft({ at }: { at: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, []);
  const label = timeLeftLabel(at, now);
  if (!label) return null;
  return <span>{label}</span>;
}
