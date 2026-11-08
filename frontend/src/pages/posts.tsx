import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CampaignSummary, type Page, type Post } from "@/api/client";
import { PostCard } from "@/components/post-card";
import { Select } from "@/components/ui/input";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";

export function QueuePage() {
  return <PostList view="queue" title="Очередь" empty="Нет постов." />;
}

export function HistoryPage() {
  return <PostList view="history" title="История" empty="Нет записей." />;
}

function PostList({ view, title, empty }: { view: "queue" | "history"; title: string; empty: string }) {
  const [status, setStatus] = useState("");
  const [campaignId, setCampaignId] = useState("");
  const campaigns = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api<Page<CampaignSummary>>("/api/campaigns"),
  });
  const posts = useQuery({
    queryKey: ["posts", view, status, campaignId],
    queryFn: () => {
      const params = new URLSearchParams({ view });
      if (status) params.set("status", status);
      if (campaignId) params.set("campaign_id", campaignId);
      return api<Page<Post>>(`/api/posts?${params.toString()}`);
    },
    refetchInterval: view === "queue" ? 4000 : false,
  });
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        <div className="flex flex-wrap gap-2">
          <Select className="w-44" value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Фильтр по статусу">
            <option value="">Все статусы</option>
            {view === "queue" ? (
              <>
                <option value="GENERATING">Генерация</option>
                <option value="PENDING_APPROVAL">Ждёт одобрения</option>
                <option value="SCHEDULED">Запланирован</option>
                <option value="PUBLISHING">Публикуется</option>
                <option value="UNKNOWN">Нужна проверка</option>
              </>
            ) : (
              <>
                <option value="PUBLISHED">Опубликован</option>
                <option value="FAILED">Ошибка</option>
                <option value="CANCELLED">Отменён</option>
              </>
            )}
          </Select>
          <Select className="w-48" value={campaignId} onChange={(event) => setCampaignId(event.target.value)} aria-label="Фильтр по кампании">
            <option value="">Все кампании</option>
            {campaigns.data?.items.map((campaign) => (
              <option key={campaign.id} value={campaign.id}>{campaign.name}</option>
            ))}
          </Select>
        </div>
      </div>
      {posts.isLoading && <LoadingState />}
      {posts.isError && <ErrorState message="Не удалось загрузить список" />}
      {posts.data && posts.data.items.length === 0 && <EmptyState title="Пусто" body={empty} />}
      <div className="space-y-3">
        {posts.data?.items.map((post) => <PostCard key={`${post.id}-${post.updated_at}`} post={post} />)}
      </div>
    </div>
  );
}
