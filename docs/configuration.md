# Конфигурация

Все настройки читаются из окружения с префиксом `ACWA_`. Пример без боевых секретов — `.env.example`.

## Режим

`ACWA_INTEGRATION_MODE=demo|live`.

В demo генератор и публикатор локальные. В live используются клиенты ниже. Ключ шифрования в live не может совпадать с ключом разработки.

`ACWA_DEMO_SEED=true` один раз создаёт демонстрационный аккаунт и приостановленную кампанию, если кампаний ещё нет.

`ACWA_AUTH_TOKEN` — пароль приложения, не короче 12 символов. Без него backend и worker не стартуют. Все маршруты, кроме `/api/health` и OAuth callback, требуют заголовок `Authorization: Bearer <пароль>`. `/docs` и `/openapi.json` тоже закрыты. Пароль не возвращается API и не пишется в логи.

## DeepSeek

Документация: [Create Chat Completion](https://api-docs.deepseek.com/api/create-chat-completion).

- База: `https://api.deepseek.com`, путь `POST /chat/completions`.
- Модели, которые принимает приложение: `deepseek-flash` и `deepseek-v4-pro`.
- Отправляются только `model`, `messages`, `temperature` (0…2), `max_tokens`, `stream=false`, `thinking.type=disabled`, `response_format.type=json_object`.
- `top_p` не отправляется: документация не рекомендует менять его вместе с temperature.
- Таймаут по умолчанию 60 секунд. Повторы только для таймаута, сети, 429 и 5xx, не больше `ACWA_DEEPSEEK_MAX_RETRIES`.
- Ключ задаётся `ACWA_DEEPSEEK_API_KEY` и в API не возвращается. В интерфейсе можно менять температуру и потолок токенов ответа (16…1024 — продуктовый предел, у API он выше).

Ответ читается как JSON `{"text": "..."}`. Другие ключи игнорируются: модель не управляет расписанием и токенами.

## Threads

Документация Meta, проверенная для этой реализации:

- [Обзор и лимиты](https://developers.facebook.com/documentation/threads/overview)
- [Токены](https://developers.facebook.com/documentation/threads/get-started/get-access-tokens-and-permissions)
- [Долгие токены](https://developers.facebook.com/documentation/threads/get-started/long-lived-tokens)
- [Публикация](https://developers.facebook.com/documentation/threads/posts)
- [Пользователь и список постов](https://developers.facebook.com/documentation/threads/reference/user)
- [Статусы контейнера](https://developers.facebook.com/documentation/threads/troubleshooting)

Хост по умолчанию `https://graph.threads.com`. Обзор Meta также допускает `graph.threads.net`; хост задаётся `ACWA_THREADS_GRAPH_BASE_URL`.

Авторизация:

1. `https://threads.com/oauth/authorize` с `threads_basic,threads_content_publish,threads_manage_insights`.
2. `POST /oauth/access_token` меняет code на короткий токен (около часа).
3. `GET /access_token?grant_type=th_exchange_token` меняет его на длинный (около 60 суток, поле `expires_in`).
4. `GET /refresh_access_token?grant_type=th_refresh_token` обновляет не истёкший длинный токен, если ему больше 24 часов.

Текстовый пост — два шага: `POST /v1.0/{user-id}/threads` с `media_type=TEXT` и `text`, затем `POST /v1.0/{user-id}/threads_publish` с `creation_id`. Необязательный `topic_tag` — тема от 1 до 50 символов без точек и амперсандов; он отправляется только с основным постом. Продолжение в комментарии — тот же двухшаговый вызов с `reply_to_id`, равным id уже опубликованного поста. Текст продолжения можно сохранить в кампании: он копируется в пост при создании. Лимит текста 500 и для поста, и для комментария. Эмодзи в подсчёте приложения занимают размер UTF-8, остальные графемы — единицу. Это чтение формулировки Meta, не отдельный официальный алгоритм. Поля для публикации в сообщество Threads в документации нет, приложение его не отправляет.

Перед публикацией читается `GET /v1.0/{user-id}/threads_publishing_limit`. Квота по умолчанию 250 постов за 86400 секунд. Статус контейнера: `GET /v1.0/{container-id}?fields=status,error_message` (`FINISHED`, `IN_PROGRESS`, `PUBLISHED`, `ERROR`, `EXPIRED`). Если контейнер уже `PUBLISHED`, пост ищется в `GET /v1.0/{user-id}/threads?fields=id,permalink,text,timestamp`.

Статистика поста: `GET /v1.0/{threads-media-id}/insights` с `metric=views,likes,replies,reposts,quotes,shares`. Нужны `threads_basic` и `threads_manage_insights`. Значения в `data[].values[0].value` — накопленные итоги поста, не прибавка за день. Пустой `data` не считается ошибкой. Если Threads отклоняет весь список из-за одной метрики, остальные запрашиваются по одной. Сбор берёт посты кампании, опубликованные вчера по её часовому поясу. Демонстрационные публикации не запрашиваются. Разрешение в приложении Meta не попадает в уже выданный токен: аккаунт нужно подключить заново, а в `ACWA_THREADS_SCOPES` должно быть `threads_manage_insights`. Ночное обучение использует тот же запрос и не добавляет метрик. Без настоящих цифр оно не меняет промпт.

GET-методы Threads по документации передают `access_token` в query. Приложение эти URL не логирует и вырезает `access_token` из текстов ошибок. POST передаёт токен в теле формы.

Для настоящего доступа нужно приложение Meta с use case Threads, Threads App ID и secret, точный redirect URI и тестеры, пока разрешения не прошли App Review. Публиковать можно только от пользователей, выдавших `threads_basic` и `threads_content_publish`. Статистика дополнительно требует `threads_manage_insights`.

Таймаут или обрыв сети на `threads_publish` не повторяется автоматически. Контейнер в `FINISHED` после уже отправленного запроса требует ручного повтора. Повтор использует тот же контейнер и тот же текст.

Реальная интеграция в этой среде не вызывалась.
