#!/usr/bin/env bash
# Offline restore drill: decrypt an off-host ASH backup and verify SQLite.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 ENCRYPTED_BACKUP.age AGE_IDENTITY_FILE" >&2
  exit 2
fi

backup=$1
identity=$2
[ -r "$backup" ] || { echo "Unreadable backup: $backup" >&2; exit 2; }
[ -r "$identity" ] || { echo "Unreadable age identity: $identity" >&2; exit 2; }
command -v age >/dev/null || { echo "age is required" >&2; exit 2; }

restored=$(mktemp "${TMPDIR:-/tmp}/ash-restore.XXXXXX.db")
trap 'rm -f "$restored"' EXIT
chmod 0600 "$restored"
age --decrypt -i "$identity" -o "$restored" "$backup"

python3 - "$restored" <<'PY'
import sqlite3,sys
path=sys.argv[1]
con=sqlite3.connect(f"file:{path}?mode=ro",uri=True)
try:
    integrity=con.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity!="ok":
        raise SystemExit(f"integrity_check failed: {integrity}")
    tables={row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    required={"trades"}
    missing=required-tables
    if missing:
        raise SystemExit(f"restore missing required tables: {sorted(missing)}")
    con.execute("SELECT COUNT(*) FROM trades").fetchone()
    print("ASH restore verification passed")
finally:
    con.close()
PY
