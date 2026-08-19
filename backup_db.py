#!/usr/bin/env python3
"""Create a consistent SQLite backup and retain a bounded daily history."""
import argparse
import os
import sqlite3

from app import BACKUP_DIR, DB, now_ny


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--retain',type=int,default=14)
    args=parser.parse_args()
    retain=max(1,min(args.retain,90))
    BACKUP_DIR.mkdir(parents=True,exist_ok=True)
    destination=BACKUP_DIR/f'arena_daily_{now_ny().strftime("%Y%m%d_%H%M%S")}.db'
    source=sqlite3.connect(DB,timeout=30)
    target=sqlite3.connect(destination)
    try: source.backup(target)
    finally:
        target.close(); source.close()
    os.chmod(destination,0o600)
    backups=sorted(BACKUP_DIR.glob('arena_daily_*.db'),key=lambda p:p.stat().st_mtime,reverse=True)
    for old in backups[retain:]:old.unlink()
    print(destination)


if __name__=='__main__':
    main()
