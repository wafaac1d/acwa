#!/bin/sh
set -eu

python -m acwa.worker &
worker_pid=$!
port="${PORT:-8000}"

uvicorn acwa.main:app --host 0.0.0.0 --port "$port" &
api_pid=$!

trap 'kill "$worker_pid" "$api_pid" 2>/dev/null || true; wait' TERM INT
wait "$api_pid"
status=$?
kill "$worker_pid" 2>/dev/null || true
wait "$worker_pid" 2>/dev/null || true
exit "$status"
