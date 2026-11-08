# Архитектура

Один процесс API и отдельный процесс worker используют пакет `acwa`. Корневой образ при старте поднимает три процесса: nginx отдаёт интерфейс и проксирует `/api` на uvicorn, worker забирает задания.

```text
frontend (React) --HTTP--> FastAPI
                              |-- campaigns, generation, publishing
                              |-- SQLAlchemy --> PostgreSQL
worker -----------------------+-- claim jobs FOR UPDATE SKIP LOCKED
                              |-- DeepSeek or demo generator
                              +-- Threads or demo publisher
```

Границы:

- `domain` — статусы, проверка кампании, политика расписания.
- `content` — длина Threads, промпт, проверка текста.
- `scheduling` — перевод локального времени IANA в UTC.
- `services` — транзакции, очередь, генерация и публикация.
- `integrations` — HTTP-клиенты и demo-двойники.
- `api` — DTO и ошибки. Таблицы наружу не отдаются.

Сущности не сериализуются во внешние API. В DeepSeek уходит собранный промпт. В Threads уходят текст, токен и, если они заданы, `topic_tag` у основного поста и `reply_to_id` у продолжения. Продолжение кампании хранится у кампании и переносится на пост в момент его создания. Сбор статистики читает `GET /{media-id}/insights` только для вчерашних постов кампании и сохраняет снимок на посте. Ночное обучение — не отдельная очередь заданий: worker при опросе смотрит `learning_next_at` в PostgreSQL, один раз собирает вчерашнюю статистику и записывает уточнение промпта.

## Посты и задания

Статус поста — жизненный цикл контента: `DRAFT`, `GENERATING`, `PENDING_APPROVAL`, `SCHEDULED`, `PUBLISHING`, `PUBLISHED`, `FAILED`, `CANCELLED`, `UNKNOWN`.

Статус задания — технический: `pending`, `running`, `succeeded`, `failed`, `cancelled`. Повторная генерация и публикация — разные `kind`: `generate`, `publish`, `reconcile`.

Захват: `SELECT … FOR UPDATE SKIP LOCKED`. Зависшее `running` старше lease возвращается в очередь. Если запрос публикации уже был отправлен, пост становится `UNKNOWN`, а задание — сверкой, а не новой отправкой.

Публикация не exactly-once. Threads не даёт такой гарантии.

## Время

В кампании хранится IANA timezone, дни 1–7 и локальные `HH:MM`. Моменты слотов и `scheduled_for` хранятся в `timestamptz` (UTC). Несуществующее локальное время при переходе на летнее время пропускается. Неоднозначное время при переходе на зимнее берёт более раннее смещение (`fold=0`).

## Ошибки API

```json
{"error": {"code": "validation_error", "message": "Проверьте поля кампании", "fields": {"name": "Укажите название"}}}
```

Списки кампаний и постов отдают `items` и `next_cursor`.
