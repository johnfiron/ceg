#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export CEG_ENV=development
export CEG_ALLOW_BROKER_ORDERS=false
if [ ! -f config.development.json ]; then
  cp config.development.example.json config.development.json
  echo "Created config.development.json with broker orders disabled."
fi
# Keep the venv off /mnt/c — Windows filesystems make venv/pip crawl.
VENV="${CEG_VENV:-$HOME/.venvs/ceg}"
if [ ! -x "$VENV/bin/python" ]; then
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install -r requirements.txt
fi
PY="$VENV/bin/python"
echo "Starting ASH Terminal V10 development web + runner..."
LAN=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\./ && $i !~ /^127\./){print $i; exit}}')
if [ -z "$LAN" ]; then
  LAN=$(python3 -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('1.1.1.1',80));print(s.getsockname()[0])" 2>/dev/null || true)
fi
echo "Dashboard (this device): http://127.0.0.1:8765"
if [ -n "$LAN" ]; then echo "Dashboard (LAN):        http://$LAN:8765"; fi
echo "Orders: disabled by default. Data: data/development/arena.db"
"$PY" runner.py &
RUNNER_PID=$!
"$PY" app.py &
WEB_PID=$!
trap 'kill "$RUNNER_PID" "$WEB_PID" 2>/dev/null || true; wait "$RUNNER_PID" "$WEB_PID" 2>/dev/null || true' EXIT INT TERM
wait -n "$RUNNER_PID" "$WEB_PID"
code=$?
echo "A development process exited $code; stopping both so failure is visible."
exit "$code"
