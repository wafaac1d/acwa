import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, ApiRequestError, type Account, type Campaign, type CampaignInput, type Page, type Post } from "@/api/client";
import { PostCard } from "@/components/post-card";
import { TimeLeft } from "@/components/time-left";
import { LearningHistoryPanel } from "@/components/learning-history";
import { YesterdayInsights } from "@/components/yesterday-insights";
import { ErrorState, LoadingState } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { campaignStatusLabel } from "@/lib/labels";
import { browserZone, todayISO } from "@/lib/utils";

const schema = z.object({
  account_id: z.string().uuid("Выберите аккаунт"),
  name: z.string().trim().min(1, "Укажите название").max(120),
  topic: z.string().trim().min(1, "Укажите тему").max(300),
  context: z.string().max(4000),
  audience: z.string().max(300),
  language: z.string().min(2).max(16),
  tone: z.string().max(200),
  goal: z.string().max(300),
  desired_length: z.enum(["short", "medium", "long"]),
  extra_instructions: z.string().max(2000),
  required_points: z.string().max(2000),
  forbidden: z.string().max(2000),
  examples: z.string().max(4000),
  allow_emoji: z.boolean(),
  allow_hashtags: z.boolean(),
  allow_links: z.boolean(),
  publish_mode: z.enum(["manual", "automatic"]),
  timezone: z.string().min(1, "Укажите часовой пояс IANA"),
  weekdays: z.array(z.number()).min(1, "Выберите хотя бы один день"),
  times_of_day: z.array(z.object({ value: z.string().regex(/^\d{2}:\d{2}$/, "Формат ЧЧ:ММ") })).min(1),
  starts_on: z.string().min(1, "Укажите дату начала"),
  ends_on: z.string(),
  threads_topic_tag: z.string().max(50, "Тема Threads не длиннее 50 символов"),
  reply_text: z.string().max(500, "Продолжение не длиннее 500 символов"),
  learning_enabled: z.boolean(),
  activate: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

const weekdays = [
  [1, "Пн"],
  [2, "Вт"],
  [3, "Ср"],
  [4, "Чт"],
  [5, "Пт"],
  [6, "Сб"],
  [7, "Вс"],
] as const;

export function CampaignEditorPage() {
  const { campaignId } = useParams();
  const isNew = !campaignId;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: () => api<{ items: Account[] }>("/api/accounts"),
  });
  const campaign = useQuery({
    queryKey: ["campaign", campaignId],
    queryFn: () => api<Campaign>(`/api/campaigns/${campaignId}`),
    enabled: !isNew,
  });
  const zones = useMemo(
    () => (typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["Europe/Moscow", "UTC"]),
    [],
  );
  const connected = (accounts.data?.items ?? []).filter((item) => item.status === "connected");
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultValues(undefined, undefined),
  });
  const accountId = connected[0]?.id;
  useEffect(() => {
    if (!campaign.data) return;
    form.reset(defaultValues(campaign.data.account_id, campaign.data));
  }, [campaign.data, form]);
  useEffect(() => {
    if (campaignId || !accountId || form.getValues("account_id")) return;
    form.setValue("account_id", accountId);
  }, [accountId, campaignId, form]);
  const times = useFieldArray({ control: form.control, name: "times_of_day" });
  const [formError, setFormError] = useState<string | null>(null);
  const [placement, setPlacement] = useState<"none" | "topic" | "community">("none");
  const [tab, setTab] = useState<"settings" | "learning">("settings");
  useEffect(() => {
    if (!campaign.data) return;
    setPlacement(campaign.data.threads_topic_tag ? "topic" : "none");
  }, [campaign.data]);
  const save = useMutation({
    mutationFn: (values: FormValues) => {
      const payload: CampaignInput = {
        ...values,
        times_of_day: values.times_of_day.map((item) => item.value),
        ends_on: values.ends_on || null,
        context: values.context,
      };
      const path = isNew ? "/api/campaigns" : `/api/campaigns/${campaignId}`;
      return api<Campaign>(path, { method: isNew ? "POST" : "PATCH", body: JSON.stringify(payload) });
    },
    onSuccess: async (saved) => {
      await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
      await queryClient.invalidateQueries({ queryKey: ["campaign", saved.id] });
      navigate(`/campaigns/${saved.id}`);
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError) {
        setFormError(reason.message);
        Object.entries(reason.fields).forEach(([field, message]) => {
          form.setError(field as keyof FormValues, { message });
        });
        return;
      }
      setFormError("Не удалось сохранить кампанию");
    },
  });
  const action = useMutation({
    mutationFn: (name: "pause" | "resume" | "archive" | "unarchive") =>
      api<Campaign>(`/api/campaigns/${campaignId}/${name}`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] }),
  });
  const trial = useMutation({
    mutationFn: () => api<Post>(`/api/campaigns/${campaignId}/trial`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["trial", campaignId] }),
  });
  const trials = useQuery({
    queryKey: ["trial", campaignId],
    queryFn: () => api<Page<Post>>(`/api/posts?campaign_id=${campaignId}&origin=trial&view=all`),
    enabled: !isNew,
    refetchInterval: 3000,
  });
  if (accounts.isLoading || (!isNew && campaign.isLoading)) return <LoadingState />;
  if (accounts.isError || campaign.isError) return <ErrorState message="Не удалось открыть редактор" />;
  const timezone = form.watch("timezone");
  const mode = form.watch("publish_mode");
  return (
    <>
    <form className="space-y-6" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link className="text-sm text-muted hover:text-ink" to="/campaigns">Кампании</Link>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight">{isNew ? "Новая кампания" : campaign.data?.name}</h2>
            {!isNew && campaign.data && (
              <Badge value={campaign.data.status} label={campaignStatusLabel(campaign.data.status)} />
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {!isNew && campaign.data?.status !== "archived" && campaign.data?.status !== "active" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("resume")}>Включить</Button>
          )}
          {!isNew && campaign.data?.status === "active" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("pause")}>Пауза</Button>
          )}
          {!isNew && campaign.data?.status !== "archived" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("archive")}>В архив</Button>
          )}
          {!isNew && campaign.data?.status === "archived" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("unarchive")}>Вернуть из архива</Button>
          )}
        </div>
      </div>
      {!isNew && (
        <div className="flex gap-1">
          <TabButton active={tab === "settings"} onClick={() => setTab("settings")}>Настройки</TabButton>
          <TabButton active={tab === "learning"} onClick={() => setTab("learning")}>Обучение</TabButton>
        </div>
      )}
      {formError && <ErrorState message={formError} />}
      {!isNew && tab === "learning" && campaignId ? (
        <LearningHistoryPanel campaignId={campaignId} nextAt={campaign.data?.learning_next_at ?? null} />
      ) : (
      <>
      {connected.length === 0 && (
        <ErrorState message="Сначала подключите аккаунт в настройках." />
      )}
      <Section title="Кампания">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Аккаунт" error={form.formState.errors.account_id?.message}>
            <Select {...form.register("account_id")}>
              <option value="">Выберите</option>
              {connected.map((account) => (
                <option key={account.id} value={account.id}>
                  {(account.display_name || account.username || "Аккаунт") + (account.is_demo ? " (демо)" : "")}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Название" error={form.formState.errors.name?.message}>
            <Input {...form.register("name")} />
          </Field>
        </div>
        <Field label="Тема" error={form.formState.errors.topic?.message}>
          <Input {...form.register("topic")} />
        </Field>
        <Field label="Контекст" error={form.formState.errors.context?.message}>
          <Textarea {...form.register("context")} />
        </Field>
        <Switch
          checked={form.watch("learning_enabled")}
          onCheckedChange={(value) => form.setValue("learning_enabled", value)}
          label="Обучение"
          hint="В полночь, по статистике за вчера."
        />
        {!isNew && campaign.data?.learning_enabled && campaign.data.learning_next_at && (
          <p className="text-sm text-muted">
            Следующий сбор {new Date(campaign.data.learning_next_at).toLocaleString()} ·{" "}
            <TimeLeft at={campaign.data.learning_next_at} />
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Аудитория"><Input {...form.register("audience")} /></Field>
          <Field label="Цель"><Input {...form.register("goal")} /></Field>
          <Field label="Язык"><Input {...form.register("language")} /></Field>
          <Field label="Тон"><Input {...form.register("tone")} /></Field>
        </div>
      </Section>
      <Section title="Публикация">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Куда">
            <Select
              value={placement}
              onChange={(event) => {
                const next = event.target.value as "none" | "topic" | "community";
                setPlacement(next);
                if (next !== "topic") form.setValue("threads_topic_tag", "");
              }}
            >
              <option value="none">Без метки</option>
              <option value="topic">Тема Threads</option>
              <option value="community">Сообщество</option>
            </Select>
          </Field>
          <Field label="Длина">
            <Select {...form.register("desired_length")}>
              <option value="short">Короткая</option>
              <option value="medium">Средняя</option>
              <option value="long">Длинная</option>
            </Select>
          </Field>
        </div>
        {placement === "topic" && (
          <Field label="Название темы" error={form.formState.errors.threads_topic_tag?.message}>
            <Input {...form.register("threads_topic_tag")} placeholder="книги" />
          </Field>
        )}
        {placement === "community" && (
          <p className="text-sm text-muted">Threads API не публикует в сообщество. Укажите тему.</p>
        )}
        <Field label="Продолжение в комментарии" error={form.formState.errors.reply_text?.message}>
          <Textarea {...form.register("reply_text")} placeholder="Необязательно" />
        </Field>
        <div className="grid gap-x-8 sm:grid-cols-3">
          <Switch checked={form.watch("allow_emoji")} onCheckedChange={(value) => form.setValue("allow_emoji", value)} label="Эмодзи" />
          <Switch checked={form.watch("allow_hashtags")} onCheckedChange={(value) => form.setValue("allow_hashtags", value)} label="Хэштеги" />
          <Switch checked={form.watch("allow_links")} onCheckedChange={(value) => form.setValue("allow_links", value)} label="Ссылки" />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Тезисы"><Textarea {...form.register("required_points")} /></Field>
          <Field label="Запрещено"><Textarea {...form.register("forbidden")} placeholder="По одной строке" /></Field>
          <Field label="Примеры"><Textarea {...form.register("examples")} /></Field>
          <Field label="Инструкции"><Textarea {...form.register("extra_instructions")} /></Field>
        </div>
      </Section>
      <Section title="Расписание" aside={timezone}>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Часовой пояс" error={form.formState.errors.timezone?.message}>
            <Input list="zones" {...form.register("timezone")} />
            <datalist id="zones">
              {zones.map((zone) => <option key={zone} value={zone} />)}
            </datalist>
          </Field>
          <Field label="Начало"><Input type="date" {...form.register("starts_on")} /></Field>
          <Field label="Окончание"><Input type="date" {...form.register("ends_on")} /></Field>
        </div>
        <fieldset>
          <legend className="mb-2 text-[13px] font-medium text-muted">Дни</legend>
          <div className="flex flex-wrap gap-1.5">
            {weekdays.map(([value, label]) => {
              const selected = form.watch("weekdays").includes(value);
              return (
                <label key={value} className={`flex h-9 min-w-9 cursor-pointer items-center justify-center rounded-md border px-2 text-sm ${selected ? "border-ink bg-ink text-white" : "border-line bg-white"}`}>
                  <input
                    className="sr-only"
                    type="checkbox"
                    checked={selected}
                    onChange={() => {
                      const current = form.getValues("weekdays");
                      form.setValue(
                        "weekdays",
                        selected ? current.filter((day) => day !== value) : [...current, value].sort(),
                        { shouldValidate: true },
                      );
                    }}
                  />
                  {label}
                </label>
              );
            })}
          </div>
          {form.formState.errors.weekdays && <p className="mt-1 text-sm text-red-800">{form.formState.errors.weekdays.message}</p>}
        </fieldset>
        <div className="space-y-2">
          <span className="block text-[13px] font-medium text-muted">Время</span>
          {times.fields.map((field, index) => (
            <div key={field.id} className="flex gap-2">
              <Input type="time" {...form.register(`times_of_day.${index}.value`)} />
              <Button type="button" variant="secondary" onClick={() => times.remove(index)}>Убрать</Button>
            </div>
          ))}
          <Button type="button" variant="secondary" onClick={() => times.append({ value: "18:00" })}>Добавить время</Button>
        </div>
        {campaign.data && campaign.data.upcoming.length > 0 && (
          <ul className="space-y-1 text-sm">
            {campaign.data.upcoming.map((slot, index) => (
              <li key={slot.scheduled_for} className="tabular-nums">
                <span className="text-muted">{index === 0 ? "Ближайший" : "Далее"}</span> {slot.local_time} · <TimeLeft at={slot.scheduled_for} />
              </li>
            ))}
          </ul>
        )}
        {campaign.data?.skipped?.map((slot) => (
          <p key={slot.slot_at} className="text-sm text-muted">{slot.local_time} · {slot.reason_label}</p>
        ))}
      </Section>
      <Section title="Режим">
        <div className="grid gap-2 sm:grid-cols-2">
          <label className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2.5 text-sm ${mode === "manual" ? "border-ink" : "border-line"}`}>
            <input type="radio" value="manual" {...form.register("publish_mode")} /> Ручное подтверждение
          </label>
          <label className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2.5 text-sm ${mode === "automatic" ? "border-ink" : "border-line"}`}>
            <input type="radio" value="automatic" {...form.register("publish_mode")} /> Автоматически
          </label>
        </div>
        <Switch checked={form.watch("activate")} onCheckedChange={(value) => form.setValue("activate", value)} label="Включить при сохранении" />
        <Button type="submit" disabled={save.isPending}>Сохранить</Button>
      </Section>
      {!isNew && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">Пробный пост</h3>
            <Button type="button" onClick={() => trial.mutate()} disabled={trial.isPending}>Сгенерировать</Button>
          </div>
          {trials.data?.items[0] ? (
            <PostCard key={trials.data.items[0].id} post={trials.data.items[0]} />
          ) : (
            <p className="text-sm text-muted">Пробных постов нет.</p>
          )}
        </section>
      )}
      </>
      )}
    </form>
    {!isNew && tab === "settings" && campaignId && <YesterdayInsights campaignId={campaignId} />}
    </>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-white font-medium text-ink shadow-card" : "text-muted hover:text-ink"}`}
    >
      {children}
    </button>
  );
}

function Section({ title, aside, children }: { title: string; aside?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-white shadow-card">
      <div className="flex items-baseline justify-between gap-3 border-b border-line px-5 py-3">
        <h3 className="text-sm font-medium">{title}</h3>
        {aside && <p className="text-xs text-muted">{aside}</p>}
      </div>
      <div className="space-y-4 p-5">{children}</div>
    </section>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-muted">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs font-normal text-red-800">{error}</span>}
    </label>
  );
}

function defaultValues(accountId: string | undefined, campaign?: Campaign): FormValues {
  if (!campaign) {
    return {
      account_id: accountId ?? "",
      name: "",
      topic: "",
      context: "",
      audience: "",
      language: "ru",
      tone: "дружелюбный и ясный",
      goal: "",
      desired_length: "medium",
      extra_instructions: "",
      required_points: "",
      forbidden: "",
      examples: "",
      allow_emoji: false,
      allow_hashtags: false,
      allow_links: false,
      publish_mode: "manual",
      timezone: browserZone(),
      weekdays: [1, 2, 3, 4, 5],
      times_of_day: [{ value: "10:00" }],
      starts_on: todayISO(),
      ends_on: "",
      threads_topic_tag: "",
      reply_text: "",
      learning_enabled: false,
      activate: false,
    };
  }
  return {
    account_id: campaign.account_id,
    name: campaign.name,
    topic: campaign.topic,
    context: campaign.context,
    audience: campaign.audience,
    language: campaign.language,
    tone: campaign.tone,
    goal: campaign.goal,
    desired_length: campaign.desired_length as FormValues["desired_length"],
    extra_instructions: campaign.extra_instructions,
    required_points: campaign.required_points,
    forbidden: campaign.forbidden,
    examples: campaign.examples,
    allow_emoji: campaign.allow_emoji,
    allow_hashtags: campaign.allow_hashtags,
    allow_links: campaign.allow_links,
    publish_mode: campaign.publish_mode as FormValues["publish_mode"],
    timezone: campaign.timezone,
    weekdays: campaign.weekdays,
    times_of_day: campaign.times_of_day.map((value) => ({ value })),
    starts_on: campaign.starts_on,
    ends_on: campaign.ends_on ?? "",
    threads_topic_tag: campaign.threads_topic_tag ?? "",
    reply_text: campaign.reply_text ?? "",
    learning_enabled: campaign.learning_enabled,
    activate: campaign.status === "active",
  };
}
