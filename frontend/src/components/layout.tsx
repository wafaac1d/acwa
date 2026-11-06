import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Health } from "@/api/client";

const links = [
  ["/", "Обзор"],
  ["/campaigns", "Кампании"],
  ["/queue", "Очередь"],
  ["/history", "История"],
  ["/settings", "Настройки"],
] as const;

export function Layout() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/api/health"),
  });
  return (
    <div className="min-h-screen bg-paper text-ink md:grid md:grid-cols-[240px_1fr]">
      <aside className="border-b border-line bg-[#ebe4d6] md:min-h-screen md:border-b-0 md:border-r">
        <div className="px-4 py-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-stone-600">acwa</p>
          <h1 className="font-serif text-3xl leading-none">Прогрев</h1>
        </div>
        <nav className="flex gap-2 overflow-x-auto px-3 pb-3 md:flex-col md:overflow-visible">
          {links.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `rounded-full px-3 py-2 text-sm font-semibold ${isActive ? "bg-ink text-white" : "text-ink hover:bg-white"}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="mx-auto w-full max-w-5xl px-4 py-6 md:px-8">
        {health.data?.integration_mode === "demo" && (
          <p className="mb-4 rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-950">
            Демонстрационный режим: посты не отправляются в Threads и DeepSeek.
          </p>
        )}
        {health.data && !health.data.auth_required && (
          <p className="mb-4 text-sm text-stone-600">
            Доступ к API не защищён паролем. Не публикуйте этот экземпляр в интернет без ACWA_AUTH_TOKEN.
          </p>
        )}
        <Outlet />
      </main>
    </div>
  );
}
