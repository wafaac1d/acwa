import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { api, ApiRequestError, type Account, type Campaign, type CampaignInput, type Page, type Post, type Settings } from "@/api/client";
import { PostCard } from "@/components/post-card";
import { TimeLeft } from "@/components/time-left";
import { YesterdayInsights } from "@/components/yesterday-insights";
import { ErrorState, LoadingState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
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
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api<Settings>("/api/settings"),
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
  return (
    <>
    <form className="space-y-6" onSubmit={form.handleSubmit((values) => save.mutate(values))}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link className="text-sm font-semibold text-moss" to="/campaigns">К списку</Link>
          <h2 className="font-serif text-4xl">{isNew ? "Новая кампания" : campaign.data?.name}</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {!isNew && campaign.data?.status !== "archived" && campaign.data?.status !== "active" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("resume")}>Включить</Button>
          )}
          {!isNew && campaign.data?.status === "active" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("pause")}>Пауза</Button>
          )}
          {!isNew && campaign.data?.status !== "archived" && (
            <Button type="button" variant="ghost" onClick={() => action.mutate("archive")}>В архив</Button>
          )}
          {!isNew && campaign.data?.status === "archived" && (
            <Button type="button" variant="secondary" onClick={() => action.mutate("unarchive")}>Вернуть из архива</Button>
          )}
        </div>
      </div>
      {formError && <ErrorState message={formError} />}
      {connected.length === 0 && (
        <ErrorState message="Сначала подключите аккаунт в настройках. Демонстрационный аккаунт тоже подходит." />
      )}
      <section className="space-y-3 rounded-3xl border border-line bg-white p-5">
        <h3 className="font-serif text-2xl">Содержание</h3>
        <Field label="Аккаунт" error={form.formState.errors.account_id?.message}>
          <select className="w-full rounded-2xl border border-line px-3 py-2" {...form.register("account_id")}>
            <option value="">Выберите</option>
            {connected.map((account) => (
              <option key={account.id} value={account.id}>
                {(account.display_name || account.username || "Аккаунт") + (account.is_demo ? " (демо)" : "")}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Название" error={form.formState.errors.name?.message}>
          <Input {...form.register("name")} />
        </Field>
        <Field label="Тема" error={form.formState.errors.topic?.message}>
          <Input {...form.register("topic")} />
        </Field>
        <Field label="Куда публиковать">
          <select
            className="w-full rounded-2xl border border-line px-3 py-2"
            value={placement}
            onChange={(event) => {
              const next = event.target.value as "none" | "topic" | "community";
              setPlacement(next);
              if (next !== "topic") form.setValue("threads_topic_tag", "");
            }}
          >
            <option value="none">Не добавлять метку</option>
            <option value="topic">Тема Threads</option>
            <option value="community">Сообщество</option>
          </select>
        </Field>
        {placement === "topic" && (
          <Field label="Название темы" error={form.formState.errors.threads_topic_tag?.message}>
            <Input {...form.register("threads_topic_tag")} placeholder="книги" />
          </Field>
        )}
        {placement === "community" && (
          <p className="text-sm text-stone-700">
            Официальный Threads API не принимает публикацию в сообщество. Выберите тему: она уйдёт параметром topic_tag.
          </p>
        )}
        {placement === "topic" && (
          <p className="text-sm text-stone-600">От 1 до 50 символов, без точки и символа &.</p>
        )}
        <Field label="Контекст" error={form.formState.errors.context?.message}>
          <Textarea {...form.register("context")} />
        </Field>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Аудитория"><Input {...form.register("audience")} /></Field>
          <Field label="Язык"><Input {...form.register("language")} /></Field>
          <Field label="Цель"><Input {...form.register("goal")} /></Field>
          <Field label="Тон и стиль"><Input {...form.register("tone")} /></Field>
        </div>
      </section>
      <section className="space-y-3 rounded-3xl border border-line bg-white p-5">
        <h3 className="font-serif text-2xl">Стиль и ограничения</h3>
        <Field label="Желаемая длина">
          <select className="w-full rounded-2xl border border-line px-3 py-2" {...form.register("desired_length")}>
            <option value="short">Короткая, около 120–200 знаков</option>
            <option value="medium">Средняя, около 250–400 знаков</option>
            <option value="long">Длинная, ближе к лимиту</option>
          </select>
        </Field>
        <p className="text-sm text-stone-600">Жёсткий лимит Threads — 500 единиц. Эмодзи считаются по байтам UTF-8. Пожелание длины его не отменяет.</p>
        <Switch checked={form.watch("allow_emoji")} onCheckedChange={(value) => form.setValue("allow_emoji", value)} label="Разрешить эмодзи" />
        <Switch checked={form.watch("allow_hashtags")} onCheckedChange={(value) => form.setValue("allow_hashtags", value)} label="Разрешить хэштеги" />
        <Switch checked={form.watch("allow_links")} onCheckedChange={(value) => form.setValue("allow_links", value)} label="Разрешить ссылки" />
        <Field label="Обязательные тезисы"><Textarea {...form.register("required_points")} /></Field>
        <Field label="Запрещённые темы и выражения, по одной строке"><Textarea {...form.register("forbidden")} /></Field>
        <Field label="Примеры удачных публикаций"><Textarea {...form.register("examples")} /></Field>
        <Field label="Дополнительные инструкции"><Textarea {...form.register("extra_instructions")} /></Field>
      </section>
      <section className="space-y-3 rounded-3xl border border-line bg-white p-5">
        <h3 className="font-serif text-2xl">Расписание</h3>
        <p className="text-sm text-stone-700">Время ниже указано в часовом поясе {timezone || "—"}, а не как фиксированное смещение UTC.</p>
        <Field label="Часовой пояс IANA" error={form.formState.errors.timezone?.message}>
          <Input list="zones" {...form.register("timezone")} />
          <datalist id="zones">
            {zones.map((zone) => <option key={zone} value={zone} />)}
          </datalist>
        </Field>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold">Дни недели</legend>
          <div className="flex flex-wrap gap-2">
            {weekdays.map(([value, label]) => {
              const selected = form.watch("weekdays").includes(value);
              return (
                <label key={value} className={`rounded-full px-3 py-2 text-sm ${selected ? "bg-ink text-white" : "bg-paper"}`}>
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
          <span className="mb-1 block text-sm font-semibold">Время публикаций</span>
          {times.fields.map((field, index) => (
            <div key={field.id} className="flex gap-2">
              <Input type="time" {...form.register(`times_of_day.${index}.value`)} />
              <Button type="button" variant="ghost" onClick={() => times.remove(index)}>Убрать</Button>
            </div>
          ))}
          <Button type="button" variant="secondary" onClick={() => times.append({ value: "18:00" })}>Добавить время</Button>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Дата начала"><Input type="date" {...form.register("starts_on")} /></Field>
          <Field label="Дата окончания, необязательно"><Input type="date" {...form.register("ends_on")} /></Field>
        </div>
        <p className="text-sm leading-6 text-stone-700">{settings.data?.missed_slot_policy}</p>
        <p className="text-sm leading-6 text-stone-700">{settings.data?.unapproved_policy}</p>
        {campaign.data && campaign.data.upcoming.length > 0 && (
          <ul className="text-sm">
            {campaign.data.upcoming.map((slot, index) => (
              <li key={slot.scheduled_for}>
                {index === 0 ? "Ближайший пост" : "Следующий слот"}: {slot.local_time} ({slot.timezone}) ·{" "}
                <TimeLeft at={slot.scheduled_for} />
              </li>
            ))}
          </ul>
        )}
        {campaign.data?.skipped?.map((slot) => (
          <p key={slot.slot_at} className="text-sm text-stone-600">{slot.local_time}: {slot.reason_label}</p>
        ))}
      </section>
      <section className="space-y-3 rounded-3xl border border-line bg-white p-5">
        <h3 className="font-serif text-2xl">Режим публикации</h3>
        <label className="flex gap-2 text-sm"><input type="radio" value="manual" {...form.register("publish_mode")} /> Ручное подтверждение</label>
        <label className="flex gap-2 text-sm"><input type="radio" value="automatic" {...form.register("publish_mode")} /> Автоматически после проверки ограничений</label>
        <Switch checked={form.watch("activate")} onCheckedChange={(value) => form.setValue("activate", value)} label="Включить расписание при сохранении" />
        <Button type="submit" disabled={save.isPending}>Сохранить</Button>
      </section>
      {!isNew && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-serif text-2xl">Пробный пост</h3>
            <Button type="button" onClick={() => trial.mutate()} disabled={trial.isPending}>Сгенерировать</Button>
          </div>
          {trials.data?.items[0] ? (
            <PostCard key={trials.data.items[0].id} post={trials.data.items[0]} />
          ) : (
            <p className="text-sm">Пробных постов ещё нет.</p>
          )}
        </section>
      )}
    </form>
    {!isNew && campaignId && <YesterdayInsights campaignId={campaignId} />}
    </>
  );
}

function Field({ label, error, children }: { label: string; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold">{label}</span>
      {children}
      {error && <span className="mt-1 block text-sm font-normal text-red-800">{error}</span>}
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
    activate: campaign.status === "active",
  };
}
