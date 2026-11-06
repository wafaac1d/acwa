export const POST_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Черновик",
  GENERATING: "Генерация",
  PENDING_APPROVAL: "Ждёт одобрения",
  SCHEDULED: "Запланирован",
  PUBLISHING: "Публикуется",
  PUBLISHED: "Опубликован",
  FAILED: "Ошибка",
  CANCELLED: "Отменён",
  UNKNOWN: "Нужна проверка",
};

export const CAMPAIGN_STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  active: "Включена",
  paused: "На паузе",
  archived: "В архиве",
};

export const ACCOUNT_STATUS_LABELS: Record<string, string> = {
  connected: "Подключён",
  needs_reauth: "Нужна повторная авторизация",
  disconnected: "Отключён",
};

export function postStatusLabel(status: string) {
  return POST_STATUS_LABELS[status] ?? status;
}

export function campaignStatusLabel(status: string) {
  return CAMPAIGN_STATUS_LABELS[status] ?? status;
}
