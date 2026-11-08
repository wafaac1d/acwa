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
    <div className="min-h-screen bg-canvas text-ink md:grid md:grid-cols-[220px_1fr]">
      <aside className="border-b border-line bg-white md:min-h-screen md:border-b-0 md:border-r">
        <div className="px-4 py-4">
          <p className="text-[15px] font-semibold">ACWA</p>
          {health.data?.integration_mode === "demo" && (
            <p className="mt-1 text-xs text-muted">Демонстрационный режим</p>
          )}
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-3 md:flex-col md:overflow-visible">
          {links.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm ${isActive ? "bg-canvas font-medium text-ink" : "text-muted hover:bg-canvas hover:text-ink"}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="mx-auto w-full max-w-5xl px-4 py-8 md:px-10">
        {health.data && !health.data.auth_required && (
          <p className="mb-6 text-sm text-muted">Доступ к API не закрыт паролем.</p>
        )}
        <Outlet />
      </main>
    </div>
  );
}
