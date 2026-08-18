#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"
echo "Starting ASH Terminal V10..."
if command -v termux-wake-lock >/dev/null 2>&1; then termux-wake-lock || true; fi
LAN=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\./ && $i !~ /^127\./){print $i; exit}}')
if [ -z "$LAN" ]; then
  LAN=$(python3 -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('1.1.1.1',80));print(s.getsockname()[0])" 2>/dev/null || true)
fi
echo "Dashboard (this device): http://127.0.0.1:8765"
if [ -n "$LAN" ]; then echo "Dashboard (LAN):        http://$LAN:8765"; fi
echo "Watchdog: respawn on crash. Stop with Ctrl-C."
while true; do
  python app.py || code=$?
  code=${code:-0}
  echo "app.py exited $code at $(date)"
  if [ "$code" = "0" ] || [ "$code" = "130" ] || [ "$code" = "143" ]; then
    echo "Clean stop ($code). Not respawning."
    break
  fi
  echo "Respawning in 5s..."
  sleep 5
done
