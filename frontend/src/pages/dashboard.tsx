import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Dashboard } from "@/api/client";
import { Card } from "@/components/ui/card";
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
    <div className="space-y-5">
      <header>
        <h2 className="font-serif text-4xl">Обзор</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-700">{data.missed_slot_policy}</p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h3 className="text-sm font-semibold text-stone-600">Аккаунт</h3>
          {account ? (
            <div className="mt-3 space-y-2">
              <Badge value={account.status} label={ACCOUNT_STATUS_LABELS[account.status] ?? account.status} />
              <p className="font-serif text-2xl">{account.display_name || account.username || "Без имени"}</p>
              <p className="text-sm text-stone-600">
                {account.username ? `@${account.username}` : "Имя пользователя недоступно"} ·{" "}
                {account.threads_user_id || "нет id"}
              </p>
              {account.is_demo && <p className="text-sm">Демонстрационный аккаунт, не Threads.</p>}
              {account.token_expires_at && (
                <p className="text-sm">Токен до {new Date(account.token_expires_at).toLocaleString("ru")}</p>
              )}
              {account.reauth_message && <p className="text-sm text-red-800">{account.reauth_message}</p>}
            </div>
          ) : (
            <p className="mt-3 text-sm">
              Аккаунт не подключён. <Link className="font-semibold text-moss" to="/settings">Открыть настройки</Link>
            </p>
          )}
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-stone-600">Кампании</h3>
          <p className="mt-3 font-serif text-4xl">{data.active_campaigns}</p>
          <p className="text-sm text-stone-600">включены, на паузе: {data.paused_campaigns}</p>
        </Card>
        <Card>
          <h3 className="text-sm font-semibold text-stone-600">Ближайшие слоты</h3>
          {data.upcoming.length === 0 ? (
            <p className="mt-3 text-sm">Нет включённых кампаний с будущим слотом.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {data.upcoming.map((slot) => (
                <li key={slot.scheduled_for}>
                  {slot.local_time} · {slot.timezone}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <section className="grid gap-4 md:grid-cols-2">
        <Card>
          <h3 className="font-serif text-2xl">Последние ошибки</h3>
          {data.recent_errors.length === 0 ? (
            <p className="mt-3 text-sm">Ошибок нет.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {data.recent_errors.map((post) => (
                <li key={post.id}>
                  <Badge value={post.status} label={postStatusLabel(post.status)} />
                  <p className="mt-1 text-sm">{post.last_error || post.campaign_name}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h3 className="font-serif text-2xl">Пропущенные слоты</h3>
          {data.skipped.length === 0 ? (
            <p className="mt-3 text-sm">Пропущенных слотов нет.</p>
          ) : (
            <ul className="mt-3 space-y-2 text-sm">
              {data.skipped.map((slot) => (
                <li key={`${slot.slot_at}-${slot.local_time}`}>
                  {slot.local_time} — {slot.reason_label}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </div>
  );
}
