import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiRequestError, type YesterdayInsights } from "@/api/client";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/states";

const METRICS = [
  ["views", "просмотры"],
  ["likes", "лайки"],
  ["replies", "ответы"],
  ["reposts", "репосты"],
  ["quotes", "цитаты"],
  ["shares", "пересылки"],
] as const;

export function YesterdayInsights({ campaignId }: { campaignId: string }) {
  const queryClient = useQueryClient();
  const insights = useQuery({
    queryKey: ["insights", campaignId],
    queryFn: () => api<YesterdayInsights>(`/api/campaigns/${campaignId}/insights/yesterday`),
  });
  const collect = useMutation({
    mutationFn: () =>
      api<YesterdayInsights>(`/api/campaigns/${campaignId}/insights/yesterday`, { method: "POST" }),
    onSuccess: (data) => queryClient.setQueryData(["insights", campaignId], data),
  });
  const data = insights.data;
  return (
    <section className="rounded-xl border border-line bg-white shadow-card">
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
        <h3 className="text-sm font-medium">Вчера</h3>
        <Button type="button" variant="secondary" onClick={() => collect.mutate()} disabled={collect.isPending}>
          {collect.isPending ? "Сбор" : "Собрать"}
        </Button>
      </div>
      <div className="space-y-3 p-5">
      {insights.isLoading && <p className="text-sm text-muted">Загрузка</p>}
      {insights.isError && <ErrorState message="Не удалось открыть статистику" />}
      {collect.isError && (
        <ErrorState message={collect.error instanceof ApiRequestError ? collect.error.message : "Не удалось собрать статистику"} />
      )}
      {data && (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            {data.date} · {data.timezone}
          </p>
          {data.notice && <p className="text-sm text-muted">{data.notice}</p>}
          {data.posts.length === 0 ? (
            <p className="text-sm text-muted">Постов не было.</p>
          ) : (
            <ul className="space-y-3">
              <li className="text-sm">{formatMetrics(data.totals, "Итого")}</li>
              {data.posts.map((post) => (
                <li key={post.post_id} className="rounded-md border border-line px-3 py-2 text-sm">
                  <p className="font-medium tabular-nums">{post.local_time}</p>
                  <p className="mt-1 line-clamp-3 whitespace-pre-wrap">{post.text || "Без текста"}</p>
                  {post.metrics ? (
                    <p className="mt-1 text-muted">{formatMetrics(post.metrics)}</p>
                  ) : (
                    <p className="mt-1 text-muted">Нет цифр.</p>
                  )}
                  {post.error && <p className="mt-1 text-red-800">{post.error}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      </div>
    </section>
  );
}

function formatMetrics(
  metrics: YesterdayInsights["totals"],
  prefix?: string,
) {
  const parts = METRICS.map(([key, label]) => {
    const value = metrics[key];
    return `${label} ${value ?? "—"}`;
  });
  return prefix ? `${prefix}: ${parts.join(", ")}` : parts.join(", ");
}
