#!/bin/sh
set -eu

python -m acwa.worker &
worker_pid=$!

uvicorn acwa.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!

python - <<'PY'
import socket
import sys
import time

for _ in range(40):
    try:
        with socket.create_connection(("127.0.0.1", 8000), 1):
            sys.exit(0)
    except OSError:
        time.sleep(0.5)
sys.exit("API не поднялся на 127.0.0.1:8000")
PY

port="${PORT:-8000}"
export PORT="$port"
envsubst '${PORT}' < /etc/nginx/acwa.conf.template > /etc/nginx/conf.d/acwa.conf
exec nginx -g 'daemon off;'
