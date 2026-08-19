#!/usr/bin/env python3
"""Dedicated ASH trading-runner process. Never import this from a web worker."""
import atexit
import os
import signal
import socket

from app import backup_db, event, now_ny, runner_loop, startup_reconcile


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
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    atexit.register(lambda: backup_db('runner-exit'))
    startup_reconcile()
    systemd_notify(f'READY=1\nSTATUS=Startup reconciliation complete at {now_ny().isoformat()}')
    runner_loop(heartbeat)


if __name__=='__main__':
    main()
