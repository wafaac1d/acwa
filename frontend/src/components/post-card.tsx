import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, ApiRequestError, type Attempt, type Post } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Textarea } from "@/components/ui/input";
import { postStatusLabel } from "@/lib/labels";

export function PostCard({ post }: { post: Post }) {
  const queryClient = useQueryClient();
  const [text, setText] = useState(post.text ?? "");
  const [replyText, setReplyText] = useState(post.reply_text ?? "");
  const [topicTag, setTopicTag] = useState(post.topic_tag ?? "");
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState<Attempt[] | null>(null);
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["posts"] });
    await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    await queryClient.invalidateQueries({ queryKey: ["trial", post.campaign_id] });
  };
  const run = useMutation({
    mutationFn: async (action: "approve" | "reject" | "cancel" | "retry" | "regenerate" | "save") => {
      setError(null);
      if (action === "save") {
        return api<Post>(`/api/posts/${post.id}`, {
          method: "PATCH",
          body: JSON.stringify({ text, reply_text: replyText, topic_tag: topicTag }),
        });
      }
      return api<Post>(`/api/posts/${post.id}/${action}`, { method: "POST" });
    },
    onSuccess: refresh,
    onError: (reason) => setError(reason instanceof ApiRequestError ? reason.message : "Не удалось обновить пост"),
  });
  const editable = ["DRAFT", "PENDING_APPROVAL", "SCHEDULED", "FAILED"].includes(post.status);
  return (
    <article className="rounded-3xl border border-line bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge value={post.status} label={postStatusLabel(post.status)} />
        <span className="text-sm text-stone-600">{post.campaign_name}</span>
        {post.is_demo_publication && <Badge value="paused" label="Демо, в Threads не отправлено" />}
      </div>
      {editable ? (
        <Textarea
          aria-label="Текст поста"
          className="mt-3"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      ) : (
        <p className="mt-3 whitespace-pre-wrap text-sm leading-6">{post.text || "Текст ещё не готов"}</p>
      )}
      {editable ? (
        <>
          <label className="mt-3 block text-sm font-semibold">
            Продолжение в комментарии
            <Textarea
              aria-label="Продолжение в комментарии"
              className="mt-1 font-normal"
              value={replyText}
              onChange={(event) => setReplyText(event.target.value)}
            />
          </label>
          <label className="mt-3 block text-sm font-semibold">
            Тег Threads
            <Input
              aria-label="Тег Threads"
              className="mt-1 font-normal"
              value={topicTag}
              onChange={(event) => setTopicTag(event.target.value)}
              placeholder="Пусто — без темы"
            />
          </label>
          <p className="mt-1 text-xs text-stone-600">
            Пустое продолжение не публикуется. Тег уходит как тема Threads. Сообщество API не принимает.
          </p>
        </>
      ) : (
        <>
          {post.reply_text && (
            <p className="mt-3 whitespace-pre-wrap text-sm leading-6">Комментарий: {post.reply_text}</p>
          )}
          {post.topic_tag && <p className="mt-2 text-sm">Тема Threads: {post.topic_tag}</p>}
        </>
      )}
      <dl className="mt-3 grid gap-1 text-xs text-stone-600 sm:grid-cols-2">
        <div>Часовой пояс: {post.timezone}</div>
        <div>Локальное время слота: {post.scheduled_local_time ?? "—"}</div>
        <div>Модель: {post.model ?? "—"}</div>
        <div>Версия промпта: {post.prompt_version ?? "—"}</div>
        {post.external_id && <div>Внешний id: {post.external_id}</div>}
        {post.container_status && <div>Контейнер Threads: {post.container_status}</div>}
      </dl>
      {post.permalink && (
        <a className="mt-2 inline-block text-sm font-semibold text-moss" href={post.permalink}>
          Открыть пост
        </a>
      )}
      {post.is_demo_publication && (
        <p className="mt-2 text-sm text-stone-700">Это демонстрационная публикация. Ссылки на Threads нет.</p>
      )}
      {post.last_error && (
        <p role="alert" className="mt-3 rounded-2xl bg-red-50 px-3 py-2 text-sm text-red-900">
          {post.last_error}
        </p>
      )}
      {error && <p className="mt-2 text-sm text-red-800">{error}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {editable && (
          <Button variant="secondary" onClick={() => run.mutate("save")} disabled={run.isPending}>
            Сохранить текст
          </Button>
        )}
        {post.status === "PENDING_APPROVAL" && (
          <>
            <Button onClick={() => run.mutate("approve")} disabled={run.isPending}>
              Одобрить
            </Button>
            <Button variant="secondary" onClick={() => run.mutate("reject")} disabled={run.isPending}>
              Отклонить
            </Button>
          </>
        )}
        {["PENDING_APPROVAL", "FAILED", "SCHEDULED", "DRAFT"].includes(post.status) && (
          <Button variant="secondary" onClick={() => run.mutate("regenerate")} disabled={run.isPending}>
            Перегенерировать
          </Button>
        )}
        {(["FAILED", "UNKNOWN"].includes(post.status) ||
          Boolean(post.external_id && post.reply_text && !post.reply_external_id && post.last_error)) && (
          <Button onClick={() => run.mutate("retry")} disabled={run.isPending}>
            {post.external_id && post.reply_text && !post.reply_external_id
              ? "Повторить комментарий"
              : "Повторить публикацию"}
          </Button>
        )}
        {!["PUBLISHED", "PUBLISHING"].includes(post.status) && (
          <Button variant="ghost" onClick={() => run.mutate("cancel")} disabled={run.isPending}>
            Отменить
          </Button>
        )}
        <Button
          variant="ghost"
          onClick={async () => setAttempts(await api<Attempt[]>(`/api/posts/${post.id}/attempts`))}
        >
          Попытки
        </Button>
      </div>
      {attempts && (
        <ul className="mt-3 space-y-2 text-sm">
          {attempts.length === 0 && <li>Попыток ещё нет.</li>}
          {attempts.map((attempt) => (
            <li key={attempt.id} className="rounded-2xl bg-paper px-3 py-2">
              {attempt.kind}: {attempt.outcome}
              {attempt.error_message ? ` — ${attempt.error_message}` : ""}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}
