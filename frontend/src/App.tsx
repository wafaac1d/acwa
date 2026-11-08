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
  if (health.isLoading || checking) return <p className="grid min-h-screen place-items-center bg-canvas text-sm text-muted">Загрузка</p>;
  if (health.isError || !health.data) {
    return <p className="grid min-h-screen place-items-center bg-canvas px-6 text-sm text-muted">Сервер недоступен.</p>;
  }
  if (unlocked && health.data.auth_required) return children;
  if (!health.data.auth_required) {
    return <p className="grid min-h-screen place-items-center bg-canvas px-6 text-sm text-muted">Задайте ACWA_AUTH_TOKEN и перезапустите сервер.</p>;
  }
  return (
    <div className="grid min-h-screen place-items-center bg-canvas px-4">
      <form
        className="w-full max-w-sm rounded-xl border border-line bg-white p-6 shadow-card"
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
        <p className="text-[15px] font-semibold">ACWA</p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight">Вход</h1>
        <label className="mt-6 block text-[13px] font-medium text-muted">
          Пароль
          <Input
            className="mt-1.5 font-normal text-ink"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {denied && <p className="mt-2 text-sm text-red-800">Пароль не подошёл.</p>}
        <Button className="mt-5 w-full" type="submit">Войти</Button>
      </form>
    </div>
  );
}
