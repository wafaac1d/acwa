# Разработка

1. Ветка от текущего main. Секреты не коммитятся: только `.env.example`.
2. Бизнес-правила остаются на backend. Frontend проверяет форму для удобства, сервер проверяет ещё раз.
3. Миграции Alembic только вперёд. Не правь уже применённую миграцию, добавь новую.
4. Внешние API в тестах заменяются заглушками. Testcontainers нужен, когда проверяются блокировки PostgreSQL.
5. Перед завершением изменения:

```bash
cd backend && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src && uv run pytest
cd frontend && npm test && npm run build
```

Если менялся HTTP-контракт, обнови `backend/openapi.json` и `frontend/src/api/schema.d.ts` командой из README. Не правь `schema.d.ts` руками.

Интерфейсные изменения проверь в браузере: пустое состояние, ошибку и основной сценарий.
