#!/usr/bin/env bash
set -euo pipefail

base=${1:-}
[[ "$base" == https://* ]] || {
  echo "usage: $0 https://vault.example.com" >&2
  exit 2
}
base=${base%/}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

status=$(curl -sS -o /dev/null -D "$tmp/session.headers" -w '%{http_code}' \
  "$base/api/auth/session")
[[ "$status" == 401 ]] || { echo "expected unauthenticated session 401, got $status" >&2; exit 1; }
awk 'BEGIN{IGNORECASE=1} /^cache-control:.*no-store/{ok=1} END{exit !ok}' "$tmp/session.headers"
awk 'BEGIN{IGNORECASE=1} /^strict-transport-security:/{ok=1} END{exit !ok}' "$tmp/session.headers"
awk 'BEGIN{IGNORECASE=1} /^content-security-policy:/{ok=1} END{exit !ok}' "$tmp/session.headers"

status=$(curl -sS -o /dev/null -w '%{http_code}' "$base/ash/api/status")
[[ "$status" == 302 || "$status" == 303 || "$status" == 401 || "$status" == 403 ]] || {
  echo "expected ASH authentication denial, got $status" >&2
  exit 1
}

status=$(curl -sS -o /dev/null -w '%{http_code}' \
  -X POST -H 'Content-Type: application/json' --data '{}' "$base/ash/api/comments")
[[ "$status" == 401 || "$status" == 403 ]] || {
  echo "expected ASH mutation denial, got $status" >&2
  exit 1
}

echo "Unauthenticated deployment security smoke checks passed"
