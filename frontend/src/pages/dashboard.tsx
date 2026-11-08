import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Dashboard } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingState } from "@/components/states";
import { ACCOUNT_STATUS_LABELS, postStatusLabel } from "@/lib/labels";

export function DashboardPage() {
  const query = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dashboard>("/api/dashboard"),
    refetchInterval: 5000,
  });
  if (query.isLoading) return <LoadingState />;
  if (query.isError || !query.data) return <ErrorState message="Не удалось загрузить обзор" />;
  const data = query.data;
  const account = data.accounts.find((item) => item.status === "connected") ?? data.accounts[0];
  return (
    <div className="space-y-8">
      <h2 className="text-2xl font-semibold tracking-tight">Обзор</h2>
      <div className="grid gap-px overflow-hidden rounded-xl border border-line bg-line shadow-card sm:grid-cols-3">
        <div className="bg-white p-5">
          <p className="text-xs text-muted">Аккаунт</p>
          {account ? (
            <div className="mt-3 space-y-2">
              <p className="text-lg font-medium">{account.display_name || account.username || "Без имени"}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Badge value={account.status} label={ACCOUNT_STATUS_LABELS[account.status] ?? account.status} />
                {account.is_demo && <Badge value="paused" label="Демо" />}
              </div>
              <p className="text-sm text-muted">
                {account.username ? `@${account.username}` : "Имя недоступно"}
                {account.token_expires_at ? ` · до ${new Date(account.token_expires_at).toLocaleDateString("ru")}` : ""}
              </p>
              {account.reauth_message && <p className="text-sm text-red-800">{account.reauth_message}</p>}
            </div>
          ) : (
            <p className="mt-3 text-sm">
              Нет аккаунта. <Link className="font-medium underline" to="/settings">Настройки</Link>
            </p>
          )}
        </div>
        <div className="bg-white p-5">
          <p className="text-xs text-muted">Кампании</p>
          <p className="mt-3 text-3xl font-semibold tabular-nums">{data.active_campaigns}</p>
          <p className="mt-1 text-sm text-muted">На паузе {data.paused_campaigns}</p>
        </div>
        <div className="bg-white p-5">
          <p className="text-xs text-muted">Ближайшие слоты</p>
          {data.upcoming.length === 0 ? (
            <p className="mt-3 text-sm text-muted">Нет</p>
          ) : (
            <ul className="mt-3 space-y-1.5 text-sm">
              {data.upcoming.map((slot) => (
                <li key={slot.scheduled_for} className="tabular-nums">
                  {slot.local_time}
                  <span className="text-muted"> · {slot.timezone}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <section className="grid gap-4 md:grid-cols-2">
        <Panel title="Ошибки" empty="Нет">
          {data.recent_errors.length > 0 && (
            <ul className="space-y-3">
              {data.recent_errors.map((post) => (
                <li key={post.id}>
                  <Badge value={post.status} label={postStatusLabel(post.status)} />
                  <p className="mt-1 text-sm">{post.last_error || post.campaign_name}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Пропущенные слоты" empty="Нет">
          {data.skipped.length > 0 && (
            <ul className="space-y-1.5 text-sm">
              {data.skipped.map((slot) => (
                <li key={`${slot.slot_at}-${slot.local_time}`}>
                  <span className="tabular-nums">{slot.local_time}</span>
                  <span className="text-muted"> · {slot.reason_label}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </section>
    </div>
  );
}

function Panel({ title, empty, children }: { title: string; empty: string; children?: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-white p-5 shadow-card">
      <h3 className="text-sm font-medium">{title}</h3>
      <div className="mt-3">{children || <p className="text-sm text-muted">{empty}</p>}</div>
    </section>
  );
}
