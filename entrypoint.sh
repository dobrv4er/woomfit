#!/bin/sh
set -e

echo "Waiting for MySQL..."

python - <<'PY'
import os, socket, time

host = os.environ.get("MYSQL_HOST", "db")
port = int(os.environ.get("MYSQL_PORT", "3306"))

for i in range(60):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        print("MySQL is reachable")
        break
    except OSError:
        print(f"Waiting {i+1}/60 for MySQL at {host}:{port} ...")
        time.sleep(1)
else:
    raise SystemExit("MySQL not reachable")
PY

python manage.py migrate --noinput
if [ "${WOOMFIT_SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo || true
fi
python manage.py runserver 0.0.0.0:8000
