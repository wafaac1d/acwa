#!/bin/sh
set -eu

python - <<'PY'
import os
import time

from sqlalchemy import create_engine, text

url = os.environ["ACWA_DATABASE_URL"]
last_error: Exception | None = None
for _ in range(30):
    try:
        engine = create_engine(url)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        engine.dispose()
        break
    except Exception as exc:  # database may still be starting
        last_error = exc
        time.sleep(1)
else:
    raise SystemExit(f"database unavailable: {last_error}")
PY

alembic upgrade head
exec "$@"
