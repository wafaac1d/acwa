# Account Warm-up (acwa)

Однопользовательское приложение для регулярной подготовки текстовых постов: кампания задаёт тему и расписание, DeepSeek пишет черновик, Threads публикует его после проверки. «Прогрев» здесь означает только заранее настроенные публикации. Нет накрутки, автолайков, автоподписок, комментариев и обхода ограничений платформы.

Это демонстрационный MVP для одного владельца. Вход закрыт паролем `ACWA_AUTH_TOKEN`.

## Быстрый старт

Нужны Docker и Docker Compose.

```bash
cp .env.example .env
```

Задайте в `.env` свой `ACWA_AUTH_TOKEN` длиной не меньше 12 символов. Этот пароль спрашивает экран входа. Затем:

```bash
docker compose up --build
```

Корневой `Dockerfile` собирает интерфейс, API и worker в один образ и слушает переменную `PORT`. На Railway достаточно этого образа: открывается страница входа, а задания обрабатывает тот же контейнер. Локальный Compose оставляет worker отдельным процессом. `frontend/Dockerfile` остаётся для отдельного nginx.

Интерфейс: http://127.0.0.1:8080  
API: http://127.0.0.1:8000/api/health  
OpenAPI: http://127.0.0.1:8000/docs

По умолчанию `ACWA_INTEGRATION_MODE=demo`. При старте создаются демонстрационный аккаунт и приостановленная кампания с пометкой, что данные учебные. В Threads и DeepSeek запросы не уходят. Реальная публикация не выполняется при миграциях, тестах и старте.

## Локальный запуск без сборки образов

Postgres:

```bash
docker compose up postgres
```

Backend, из каталога `backend` (нужен [uv](https://docs.astral.sh/uv/) и Python 3.12):

```bash
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn acwa.main:app --reload --port 8000
uv run python -m acwa.worker
```

Frontend, из каталога `frontend`:

```bash
npm install
npm run dev
```

Интерфейс разработки: http://127.0.0.1:5173. Vite проксирует `/api` на backend.

## Проверки

```bash
cd backend && uv run ruff check src tests && uv run mypy src && uv run pytest
cd frontend && npm test && npm run build
```

Интеграционные тесты backend сами поднимают PostgreSQL через Testcontainers. Для Playwright нужен уже запущенный стек:

```bash
cd frontend && ACWA_E2E_BASE_URL=http://127.0.0.1:8080 npm run e2e
```

Обновить TypeScript-типы из OpenAPI:

```bash
cd backend && uv run python -c 'import json; from acwa.main import app; json.dump(app.openapi(), open("openapi.json","w"), ensure_ascii=False)'
cd frontend && npm run generate:api
```

## Режим demo и режим live

`demo` проверяет весь сценарий локально. Тексты начинаются с `[демо`, публикация получает id `demo:` и не имеет ссылки на Threads.

`live` вызывает официальные API. Для него нужны ключ DeepSeek, Threads App ID и App Secret, redirect URI в кабинете Meta и свой Fernet-ключ вместо ключа из `.env.example`. Приложение откажется стартовать в live-режиме с ключом разработки.

Подробности: `docs/configuration.md`, `docs/product.md`, `docs/architecture.md`.
