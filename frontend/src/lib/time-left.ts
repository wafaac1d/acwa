const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export function timeLeftLabel(targetIso: string, now = Date.now()): string {
  const target = new Date(targetIso).getTime();
  if (Number.isNaN(target)) return "";
  const diff = target - now;
  if (diff <= 0) return "время уже наступило";
  if (diff < MINUTE) return "осталось меньше минуты";
  const days = Math.floor(diff / DAY);
  const hours = Math.floor((diff % DAY) / HOUR);
  const minutes = Math.floor((diff % HOUR) / MINUTE);
  if (days > 0) return hours > 0 ? `осталось ${days} д ${hours} ч` : `осталось ${days} д`;
  if (hours > 0) return minutes > 0 ? `осталось ${hours} ч ${minutes} мин` : `осталось ${hours} ч`;
  return `осталось ${minutes} мин`;
}
