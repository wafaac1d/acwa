import { useQuery } from "@tanstack/react-query";
import { api, type LearningEvent, type LearningHistory } from "@/api/client";
import { TimeLeft } from "@/components/time-left";
import { ErrorState, LoadingState } from "@/components/states";

export function LearningHistoryPanel({
  campaignId,
  nextAt,
}: {
  campaignId: string;
  nextAt: string | null;
}) {
  const history = useQuery({
    queryKey: ["learning", campaignId],
    queryFn: () => api<LearningHistory>(`/api/campaigns/${campaignId}/learning`),
  });
  return (
    <section className="rounded-xl border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line px-5 py-3">
        <h3 className="text-sm font-medium">История</h3>
        {nextAt && (
          <p className="text-xs text-muted">
            Следующий сбор {new Date(nextAt).toLocaleString()} · <TimeLeft at={nextAt} />
          </p>
        )}
      </div>
      <div className="p-5">
        {history.isLoading && <LoadingState />}
        {history.isError && <ErrorState message="Не удалось открыть историю обучения" />}
        {history.data && history.data.items.length === 0 && (
          <p className="text-sm text-muted">Записей нет.</p>
        )}
        {history.data && history.data.items.length > 0 && (
          <ol className="space-y-4">
            {history.data.items.map((item) => (
              <li key={item.id} className="border-b border-line pb-4 last:border-b-0 last:pb-0">
                <Event item={item} />
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function Event({ item }: { item: LearningEvent }) {
  return (
    <article className="space-y-2">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <time className="text-sm font-medium tabular-nums">{new Date(item.created_at).toLocaleString()}</time>
        <span className="text-xs text-muted">{item.changed ? "Уточнение изменилось" : "Без изменений"}</span>
        {item.covered_on && <span className="text-xs text-muted">за {item.covered_on}</span>}
      </div>
      <p className="text-sm leading-6">{item.reason}</p>
      {item.changed && (
        <div className="grid gap-3 sm:grid-cols-2">
          <Note label="Было" text={item.previous_notes} />
          <Note label="Стало" text={item.notes} />
        </div>
      )}
    </article>
  );
}

function Note({ label, text }: { label: string; text: string }) {
  return (
    <div className="rounded-md bg-canvas px-3 py-2">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-6">{text.trim() || "Пусто"}</p>
    </div>
  );
}
