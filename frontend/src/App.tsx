import { useEffect, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, accessToken, clearAccessToken, saveAccessToken, setUnauthorizedHandler, type Health } from "@/api/client";
import { Layout } from "@/components/layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DashboardPage } from "@/pages/dashboard";
import { CampaignsPage } from "@/pages/campaigns";
import { CampaignEditorPage } from "@/pages/campaign-editor";
import { HistoryPage, QueuePage } from "@/pages/posts";
import { SettingsPage } from "@/pages/settings";

const client = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export function App() {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AccessGate>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/campaigns" element={<CampaignsPage />} />
              <Route path="/campaigns/new" element={<CampaignEditorPage />} />
              <Route path="/campaigns/:campaignId" element={<CampaignEditorPage />} />
              <Route path="/queue" element={<QueuePage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </AccessGate>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function AccessGate({ children }: { children: ReactNode }) {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/api/health") });
  const [password, setPassword] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [checking, setChecking] = useState(Boolean(accessToken()));
  const [denied, setDenied] = useState(false);
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUnlocked(false);
      setDenied(true);
    });
  }, []);
  useEffect(() => {
    if (!accessToken()) {
      setChecking(false);
      return;
    }
    api("/api/settings")
      .then(() => {
        setUnlocked(true);
        setDenied(false);
      })
      .catch(() => {
        clearAccessToken();
        setUnlocked(false);
      })
      .finally(() => setChecking(false));
  }, []);
  if (health.isLoading || checking) return <p className="p-8">Загрузка…</p>;
  if (health.isError || !health.data) {
    return <p className="p-8">Не удалось связаться с сервером. Проверьте, что backend запущен.</p>;
  }
  if (unlocked && health.data.auth_required) return children;
  if (!health.data.auth_required) {
    return <p className="p-8">Сервер запущен без пароля. Задайте ACWA_AUTH_TOKEN и перезапустите его.</p>;
  }
  return (
    <form
      className="mx-auto mt-16 max-w-md space-y-3 rounded-3xl bg-white p-6"
      onSubmit={(event) => {
        event.preventDefault();
        setDenied(false);
        saveAccessToken(password);
        api("/api/settings")
          .then(() => setUnlocked(true))
          .catch(() => {
            clearAccessToken();
            setDenied(true);
          });
      }}
    >
      <h1 className="font-serif text-3xl">Вход</h1>
      <p className="text-sm">Пароль задаётся на сервере в ACWA_AUTH_TOKEN. Это не пароль Threads и не ключ DeepSeek.</p>
      <label className="block text-sm font-semibold">
        Пароль
        <Input
          className="mt-1 font-normal"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </label>
      {denied && <p className="text-sm text-red-800">Пароль не подошёл.</p>}
      <Button type="submit">Войти</Button>
    </form>
  );
}
