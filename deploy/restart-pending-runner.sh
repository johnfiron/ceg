#!/usr/bin/env bash
set -euo pipefail

marker=/var/lib/ash/pending-runner-release
[ -s "$marker" ] || exit 0
wanted=$(sed -n '1p' "$marker")
current=$(basename "$(readlink -f /opt/ash/current)")
if [ "$wanted" != "$current" ]; then
  echo "pending runner release $wanted does not match active web release $current" >&2
  exit 1
fi
systemctl restart ash-runner.service
for _ in $(seq 1 45); do
  state=$(systemctl is-active ash-runner.service || true)
  [ "$state" = active ] && break
  sleep 2
done
[ "$(systemctl is-active ash-runner.service || true)" = active ]
rm -f "$marker"
