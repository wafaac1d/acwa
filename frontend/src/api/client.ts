import type { components } from "./schema";

export type Health = components["schemas"]["HealthResponse"];
export type Settings = components["schemas"]["SettingsRead"];
export type Account = components["schemas"]["AccountRead"];
export type Campaign = components["schemas"]["CampaignRead"];
export type CampaignSummary = components["schemas"]["CampaignSummary"];
export type CampaignInput = components["schemas"]["CampaignWrite"];
export type Post = components["schemas"]["PostRead"];
export type Attempt = components["schemas"]["AttemptRead"];
export type Dashboard = components["schemas"]["DashboardRead"];
export type YesterdayInsights = components["schemas"]["YesterdayInsights"];
export type LearningEvent = components["schemas"]["LearningEventRead"];
export type LearningHistory = components["schemas"]["LearningHistory"];
export type Page<T> = { items: T[]; next_cursor: string | null };

export class ApiRequestError extends Error {
  fields: Record<string, string>;

  constructor(message: string, fields: Record<string, string> = {}) {
    super(message);
    this.fields = fields;
  }
}

const TOKEN_KEY = "acwa.accessToken";

export function accessToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function saveAccessToken(value: string) {
  sessionStorage.setItem(TOKEN_KEY, value);
}

export function clearAccessToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = accessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    clearAccessToken();
    onUnauthorized?.();
  }
  if (response.ok) {
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }
  let message = "Не удалось выполнить запрос";
  let fields: Record<string, string> = {};
  try {
    const body = (await response.json()) as { error?: { message?: string; fields?: Record<string, string> } };
    message = body.error?.message || message;
    fields = body.error?.fields ?? {};
  } catch {
    message = "Сервер вернул непонятную ошибку";
  }
  throw new ApiRequestError(message, fields);
}
