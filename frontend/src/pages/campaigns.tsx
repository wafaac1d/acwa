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
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold tracking-tight">Кампании</h2>
        <Button asChild>
          <Link to="/campaigns/new">Новая кампания</Link>
        </Button>
      </div>
      {items.length === 0 ? (
        <EmptyState title="Кампаний нет" body="Создайте кампанию и проверьте пробный пост." />
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-white shadow-card">
          {items.map((campaign) => (
            <li key={campaign.id}>
              <Link to={`/campaigns/${campaign.id}`} className="flex items-center justify-between gap-4 px-4 py-3.5 hover:bg-canvas">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-medium">{campaign.name}</h3>
                    <Badge value={campaign.status} label={campaignStatusLabel(campaign.status)} />
                  </div>
                  <p className="mt-0.5 truncate text-sm text-muted">{campaign.topic}</p>
                </div>
                <p className="shrink-0 text-right text-sm text-muted">
                  {campaign.publish_mode === "manual" ? "Вручную" : "Авто"}
                  {campaign.next_slot && (
                    <>
                      <span className="mt-0.5 block tabular-nums text-ink">{campaign.next_slot.local_time}</span>
                      <TimeLeft at={campaign.next_slot.scheduled_for} />
                    </>
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
