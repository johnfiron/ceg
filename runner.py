#!/usr/bin/env python3
"""Dedicated ASH trading-runner process. Never import this from a web worker."""
import atexit
import fcntl
import os
import signal
import socket
from pathlib import Path

from app import ROOT, backup_db, event, meta_set, now_ny, runner_loop, startup_reconcile


_runner_lock=None


def acquire_runner_lock():
    """Hold a process lock so overlapping releases can never place duplicate orders."""
    global _runner_lock
    data=Path(os.environ.get('CEG_DATA_DIR') or (ROOT/'data'/'production'))
    data.mkdir(parents=True,exist_ok=True)
    handle=open(data/'runner.lock','a+',encoding='utf-8')
    try: fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise RuntimeError('another ASH trading runner already holds the process lock')
    handle.seek(0); handle.truncate(); handle.write(str(os.getpid())); handle.flush()
    _runner_lock=handle


def systemd_notify(message):
    address=os.environ.get('NOTIFY_SOCKET')
    if not address:return
    if address.startswith('@'):address='\0'+address[1:]
    sock=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM)
    try:sock.sendto(message.encode(),address)
    finally:sock.close()


def stop(signum,_frame):
    event(f'Runner stopping on signal {signum}')
    raise SystemExit(0)


def heartbeat(now):
    systemd_notify(f'WATCHDOG=1\nSTATUS=Runner heartbeat {now.isoformat()}')


def main():
    acquire_runner_lock()
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    atexit.register(lambda: backup_db('runner-exit'))
    startup_reconcile()
    meta_set('runner_release',ROOT.name)
    systemd_notify(f'READY=1\nSTATUS=Startup reconciliation complete at {now_ny().isoformat()}')
    runner_loop(heartbeat)


if __name__=='__main__':
    main()
