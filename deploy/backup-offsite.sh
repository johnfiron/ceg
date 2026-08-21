#!/usr/bin/env bash
set -euo pipefail

ASH_VENV=${ASH_VENV:-/opt/ash/venv}
ASH_RELEASE=${ASH_RELEASE:-/opt/ash/current}
RECIPIENT_FILE=${ASH_BACKUP_RECIPIENT_FILE:-/etc/ash/backup-recipient.txt}
REMOTE=${ASH_RCLONE_REMOTE:-}
RCLONE_CONFIG=${RCLONE_CONFIG:-/var/lib/ash/offsite/rclone.conf}
RETAIN=${ASH_LOCAL_BACKUP_RETAIN:-14}

backup=$("$ASH_VENV/bin/python" "$ASH_RELEASE/backup_db.py" --retain "$RETAIN")
if [ ! -s "$backup" ]; then
  echo "ASH backup was not created: $backup" >&2
  exit 1
fi

integrity=$("$ASH_VENV/bin/python" - "$backup" <<'PY'
import sqlite3,sys
con=sqlite3.connect(f"file:{sys.argv[1]}?mode=ro",uri=True)
try:
    print(con.execute("PRAGMA integrity_check").fetchone()[0])
finally:
    con.close()
PY
)
if [ "$integrity" != ok ]; then
  echo "SQLite integrity check failed: $integrity" >&2
  exit 1
fi

if [ -z "$REMOTE" ]; then
  echo "ASH_RCLONE_REMOTE is required; local backup retained at $backup" >&2
  exit 2
fi
if [ ! -r "$RECIPIENT_FILE" ]; then
  echo "Missing age recipient: $RECIPIENT_FILE" >&2
  exit 2
fi
command -v age >/dev/null || { echo "age is required" >&2; exit 2; }
command -v rclone >/dev/null || { echo "rclone is required" >&2; exit 2; }
[ -r "$RCLONE_CONFIG" ] || { echo "Missing rclone config: $RCLONE_CONFIG" >&2; exit 2; }

encrypted=$(mktemp /var/lib/ash/backups/.ash-offsite.XXXXXX.age)
trap 'rm -f "$encrypted"' EXIT
age -r "$(tr -d '\r\n' < "$RECIPIENT_FILE")" -o "$encrypted" "$backup"
chmod 0600 "$encrypted"
remote_file="${REMOTE%/}/$(basename "$backup").age"
rclone copyto "$encrypted" "$remote_file" --config "$RCLONE_CONFIG" --checksum

local_size=$(stat -c %s "$encrypted")
remote_size=$(rclone size "$remote_file" --config "$RCLONE_CONFIG" --json |
  "$ASH_VENV/bin/python" -c 'import json,sys; print(json.load(sys.stdin)["bytes"])')
[ "$local_size" = "$remote_size" ] || {
  echo "Off-host ASH backup size mismatch" >&2
  exit 1
}

echo "ASH backup verified and uploaded: $(basename "$remote_file")"
