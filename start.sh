#!/data/data/com.termux/files/usr/bin/bash
cd "$(dirname "$0")"
export CEG_ENV=development
export CEG_ALLOW_BROKER_ORDERS=false
if [ ! -f config.development.json ]; then
  cp config.development.example.json config.development.json
  echo "Created config.development.json with broker orders disabled."
fi
echo "Starting ASH Terminal V10..."
if command -v termux-wake-lock >/dev/null 2>&1; then termux-wake-lock || true; fi
LAN=$(hostname -I 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i ~ /^[0-9]+\./ && $i !~ /^127\./){print $i; exit}}')
if [ -z "$LAN" ]; then
  LAN=$(python3 -c "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('1.1.1.1',80));print(s.getsockname()[0])" 2>/dev/null || true)
fi
echo "Dashboard (this device): http://127.0.0.1:8765"
if [ -n "$LAN" ]; then echo "Dashboard (LAN):        http://$LAN:8765"; fi
echo "Orders: disabled by default. Web and trading runner are separate processes."
python runner.py &
RUNNER_PID=$!
python app.py &
WEB_PID=$!
trap 'kill "$RUNNER_PID" "$WEB_PID" 2>/dev/null || true; wait "$RUNNER_PID" "$WEB_PID" 2>/dev/null || true' EXIT INT TERM
wait -n "$RUNNER_PID" "$WEB_PID"
code=$?
echo "A process exited $code; stopping both so failure is visible."
exit "$code"
