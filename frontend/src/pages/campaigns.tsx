import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Page, type CampaignSummary } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/states";
import { TimeLeft } from "@/components/time-left";
import { campaignStatusLabel } from "@/lib/labels";

export function CampaignsPage() {
  const query = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => api<Page<CampaignSummary>>("/api/campaigns"),
  });
  if (query.isLoading) return <LoadingState />;
  if (query.isError) return <ErrorState message="Не удалось загрузить кампании" />;
  const items = query.data?.items ?? [];
  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-3">
        <h2 className="font-serif text-4xl">Кампании</h2>
        <Button asChild>
          <Link to="/campaigns/new">Новая кампания</Link>
        </Button>
      </div>
      {items.length === 0 ? (
        <EmptyState
          title="Кампаний пока нет"
          body="Создайте кампанию, проверьте пробный пост и только потом включайте расписание."
        />
      ) : (
        <ul className="space-y-3">
          {items.map((campaign) => (
            <li key={campaign.id}>
              <Link to={`/campaigns/${campaign.id}`} className="block rounded-3xl border border-line bg-white p-4 hover:border-moss">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-serif text-2xl">{campaign.name}</h3>
                  <Badge value={campaign.status} label={campaignStatusLabel(campaign.status)} />
                </div>
                <p className="mt-1 text-sm text-stone-700">{campaign.topic}</p>
                <p className="mt-2 text-sm text-stone-600">
                  {campaign.publish_mode === "manual" ? "Ручное подтверждение" : "Автопубликация"} ·{" "}
                  {campaign.timezone}
                  {campaign.next_slot ? (
                    <>
                      {" "}
                      · следующий пост {campaign.next_slot.local_time} · <TimeLeft at={campaign.next_slot.scheduled_for} />
                    </>
                  ) : (
                    ""
                  )}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
