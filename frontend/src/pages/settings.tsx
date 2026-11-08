import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiRequestError, type Account, type Settings } from "@/api/client";
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
      setMessage("Сохранено");
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
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold tracking-tight">Настройки</h2>
      {message && <p className="text-sm text-muted">{message}</p>}
      <section className="rounded-xl border border-line bg-white shadow-card">
        <div className="flex flex-col items-start gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-sm font-medium">Threads</h3>
            <p className="mt-0.5 text-xs text-muted">
              {current.integration_mode === "demo" ? "Демо" : "Live"} · {current.threads.scopes.join(", ")}
            </p>
          </div>
          {current.integration_mode === "demo" ? (
            <Button onClick={() => connectDemo.mutate()} disabled={connectDemo.isPending}>Подключить демонстрационный аккаунт</Button>
          ) : (
            <Button onClick={() => startOauth.mutate()} disabled={startOauth.isPending || !current.threads.configured}>Подключить Threads</Button>
          )}
        </div>
        <ul className="divide-y divide-line">
          {accounts.data?.items.map((account) => (
            <li key={account.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <strong className="font-medium">{account.display_name || account.username || "Аккаунт"}</strong>
                  <Badge value={account.status} label={ACCOUNT_STATUS_LABELS[account.status] ?? account.status} />
                  {account.is_demo && <Badge value="paused" label="Демо" />}
                </div>
                <p className="mt-1 text-sm text-muted">
                  {account.username ? `@${account.username}` : "Имя недоступно"}
                  {account.token_expires_at ? ` · до ${new Date(account.token_expires_at).toLocaleDateString("ru")}` : ""}
                </p>
                {account.reauth_message && <p className="mt-1 text-sm text-red-800">{account.reauth_message}</p>}
              </div>
              {account.status === "connected" && (
                <Button variant="secondary" onClick={() => disconnect.mutate(account.id)}>Отключить</Button>
              )}
            </li>
          ))}
          {accounts.data?.items.length === 0 && <li className="px-5 py-4 text-sm text-muted">Аккаунтов нет.</li>}
        </ul>
      </section>
      <section className="space-y-4 rounded-xl border border-line bg-white p-5 shadow-card">
        <div>
          <h3 className="text-sm font-medium">Генерация</h3>
          <p className="mt-0.5 text-xs text-muted">
            {current.deepseek.configured ? current.generation.model : "DeepSeek не настроен"}
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label>
            <Label>Температура</Label>
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
            <Label>Токены ответа</Label>
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
      </section>
    </div>
  );
}
