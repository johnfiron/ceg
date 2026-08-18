#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "Created config.json from example. Add Alpaca paper keys when you want tape."
fi
# Keep the venv off /mnt/c — Windows filesystems make venv/pip crawl.
VENV="${CEG_VENV:-$HOME/.venvs/ceg}"
if [ ! -x "$VENV/bin/python" ]; then
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install -r requirements.txt
fi
PY="$VENV/bin/python"
echo "Starting ASH Terminal V10..."
LAN=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\./ && $i !~ /^127\./){print $i; exit}}')
if [ -z "$LAN" ]; then
  LAN=$(python3 -c "import socket;s=socket.socket(socket.AF_INET,SOCK_DGRAM);s.connect(('1.1.1.1',80));print(s.getsockname()[0])" 2>/dev/null || true)
fi
echo "Dashboard (this device): http://127.0.0.1:8765"
if [ -n "$LAN" ]; then echo "Dashboard (LAN):        http://$LAN:8765"; fi
echo "Watchdog: respawn on crash. Stop with Ctrl-C."
while true; do
  "$PY" app.py || code=$?
  code=${code:-0}
  echo "app.py exited $code at $(date)"
  if [ "$code" = "0" ] || [ "$code" = "130" ] || [ "$code" = "143" ]; then
    echo "Clean stop ($code). Not respawning."
    break
  fi
  echo "Respawning in 5s..."
  sleep 5
done
