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
    <section className="space-y-3 rounded-3xl border border-line bg-white p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="font-serif text-2xl">Статистика за вчера</h3>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-stone-700">
            Посты, опубликованные вчера по часовому поясу кампании. Цифры — текущие итоги Threads по каждому посту, не прибавка за день.
          </p>
        </div>
        <Button type="button" onClick={() => collect.mutate()} disabled={collect.isPending}>
          {collect.isPending ? "Собираем" : "Собрать"}
        </Button>
      </div>
      {insights.isLoading && <p className="text-sm">Загружаем сохранённую статистику.</p>}
      {insights.isError && <ErrorState message="Не удалось открыть статистику" />}
      {collect.isError && (
        <ErrorState message={collect.error instanceof ApiRequestError ? collect.error.message : "Не удалось собрать статистику"} />
      )}
      {data && (
        <div className="space-y-3">
          <p className="text-sm text-stone-700">
            {data.date}, {data.timezone}
          </p>
          {data.notice && <p className="text-sm leading-6 text-stone-700">{data.notice}</p>}
          {data.posts.length === 0 ? (
            <p className="text-sm">Вчера опубликованных постов нет.</p>
          ) : (
            <ul className="space-y-3">
              <li className="text-sm text-stone-700">{formatMetrics(data.totals, "Итого")}</li>
              {data.posts.map((post) => (
                <li key={post.post_id} className="rounded-2xl border border-line px-3 py-2 text-sm">
                  <p className="font-semibold">{post.local_time}</p>
                  <p className="mt-1 line-clamp-3 whitespace-pre-wrap">{post.text || "Без текста"}</p>
                  {post.metrics ? (
                    <p className="mt-1 text-stone-700">{formatMetrics(post.metrics)}</p>
                  ) : (
                    <p className="mt-1 text-stone-600">Статистика ещё не собрана.</p>
                  )}
                  {post.error && <p className="mt-1 text-red-800">{post.error}</p>}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
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
