#!/data/data/com.termux/files/usr/bin/bash
set -e
echo "=== ASH Terminal V7 setup ==="
pkg update -y
pkg install -y python python-pip
python -m pip install -r requirements.txt
chmod +x start.sh
echo
echo "Setup complete. Run: bash start.sh"
