import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiRequestError, type Account, type Settings } from "@/api/client";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ErrorState, LoadingState } from "@/components/states";
import { ACCOUNT_STATUS_LABELS } from "@/lib/labels";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<Settings>("/api/settings") });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: () => api<{ items: Account[] }>("/api/accounts") });
  const [temperature, setTemperature] = useState<number | null>(null);
  const [maxTokens, setMaxTokens] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: () =>
      api<Settings>("/api/settings", {
        method: "PATCH",
        body: JSON.stringify({
          temperature: temperature ?? settings.data?.generation.temperature,
          max_tokens: maxTokens ?? settings.data?.generation.max_tokens,
        }),
      }),
    onSuccess: () => {
      setMessage("Параметры генерации сохранены. Ключ DeepSeek остаётся только на сервере.");
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (reason) => setMessage(reason instanceof ApiRequestError ? reason.message : "Не удалось сохранить"),
  });
  const connectDemo = useMutation({
    mutationFn: () => api<Account>("/api/accounts/demo", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["accounts"] }),
    onError: (reason) => setMessage(reason instanceof ApiRequestError ? reason.message : "Не удалось подключить демо"),
  });
  const startOauth = useMutation({
    mutationFn: () => api<{ authorization_url: string }>("/api/accounts/threads/start", { method: "POST" }),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: (reason) => setMessage(reason instanceof ApiRequestError ? reason.message : "OAuth недоступен"),
  });
  const disconnect = useMutation({
    mutationFn: (id: string) => api<Account>(`/api/accounts/${id}/disconnect`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["accounts"] }),
  });
  if (settings.isLoading || accounts.isLoading) return <LoadingState />;
  if (settings.isError || !settings.data) return <ErrorState message="Не удалось загрузить настройки" />;
  const current = settings.data;
  return (
    <div className="space-y-5">
      <h2 className="font-serif text-4xl">Настройки</h2>
      {message && <p className="text-sm">{message}</p>}
      <Card className="space-y-3">
        <h3 className="font-serif text-2xl">Режим</h3>
        <p className="text-sm">Сейчас: {current.integration_mode === "demo" ? "демо" : "настоящие интеграции"}.</p>
        <p className="text-sm text-stone-700">
          Переключение делается переменной ACWA_INTEGRATION_MODE. Из интерфейса нельзя случайно включить настоящую публикацию.
        </p>
        <p className="text-sm">{current.public_deployment_ready ? "" : "Приложение не готово к публичному размещению без защиты доступа."}</p>
      </Card>
      <Card className="space-y-3">
        <h3 className="font-serif text-2xl">Threads</h3>
        <p className="text-sm">Приложение Meta настроено: {current.threads.configured ? "да" : "нет"}.</p>
        <p className="text-sm">Разрешения: {current.threads.scopes.join(", ")}. Лимит текста: {current.threads.text_limit}.</p>
        <p className="text-sm">Redirect URI: {current.threads.redirect_uri}</p>
        {current.integration_mode === "demo" ? (
          <Button onClick={() => connectDemo.mutate()} disabled={connectDemo.isPending}>Подключить демонстрационный аккаунт</Button>
        ) : (
          <Button onClick={() => startOauth.mutate()} disabled={startOauth.isPending || !current.threads.configured}>Подключить Threads</Button>
        )}
        <ul className="space-y-3">
          {accounts.data?.items.map((account) => (
            <li key={account.id} className="rounded-2xl bg-paper p-3">
              <div className="flex flex-wrap items-center gap-2">
                <strong>{account.display_name || account.username || "Аккаунт"}</strong>
                <Badge value={account.status} label={ACCOUNT_STATUS_LABELS[account.status] ?? account.status} />
                {account.is_demo && <Badge value="paused" label="Демо" />}
              </div>
              <p className="mt-1 text-sm text-stone-700">
                {account.username ? `@${account.username}` : "Имя недоступно"} · id {account.threads_user_id || "—"}
              </p>
              {account.token_expires_at && <p className="text-sm">Токен действует до {new Date(account.token_expires_at).toLocaleString("ru")}</p>}
              {account.reauth_message && <p className="text-sm text-red-800">{account.reauth_message}</p>}
              {account.status === "connected" && (
                <Button className="mt-2" variant="secondary" onClick={() => disconnect.mutate(account.id)}>Отключить</Button>
              )}
            </li>
          ))}
          {accounts.data?.items.length === 0 && <li className="text-sm">Подключённых аккаунтов нет.</li>}
        </ul>
      </Card>
      <Card className="space-y-3">
        <h3 className="font-serif text-2xl">Генерация</h3>
        <p className="text-sm">
          DeepSeek {current.deepseek.configured ? "настроен" : "не настроен"}. Модель {current.generation.model}. Ключ в интерфейс не передаётся.
        </p>
        <p className="text-sm">Адрес API: {current.deepseek.base_url}. Версия промпта: {current.generation.prompt_version}.</p>
        <div className="grid gap-3 md:grid-cols-2">
          <label>
            <Label>Температура, от 0 до 2</Label>
            <Input
              type="number"
              min={0}
              max={2}
              step={0.1}
              defaultValue={current.generation.temperature}
              onChange={(event) => setTemperature(Number(event.target.value))}
            />
          </label>
          <label>
            <Label>Максимум токенов ответа, до 1024</Label>
            <Input
              type="number"
              min={16}
              max={1024}
              defaultValue={current.generation.max_tokens}
              onChange={(event) => setMaxTokens(Number(event.target.value))}
            />
          </label>
        </div>
        <Button onClick={() => save.mutate()} disabled={save.isPending}>Сохранить параметры</Button>
        <p className="text-sm leading-6 text-stone-700">{current.missed_slot_policy}</p>
      </Card>
    </div>
  );
}
