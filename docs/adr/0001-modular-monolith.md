# Стек

Задание зафиксировало Python, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, React и Vite. Ранний набросок на Kotlin не использовался: репозиторий был пуст, а итоговая спецификация выбрала Python.

API и worker — один пакет. Отдельные сервисы, брокер и Redis не нужны: очередь — таблица `jobs` с `FOR UPDATE SKIP LOCKED`.

Сервисы синхронные. Так проще граница транзакции SQLAlchemy и общий код API и worker. HTTP-клиент — синхронный httpx. Нагрузка MVP этому соответствует.
