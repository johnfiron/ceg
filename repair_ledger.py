#!/usr/bin/env python3
"""Audit or atomically repair ASH's local ledger from Alpaca paper fills."""
import argparse
import hashlib
import json

from app import (
    ah,
    apply_broker_ledger_repair,
    backup_db,
    broker_ledger_repair_plan,
    now_ny,
    paper_api_url,
    getj,
)


def load_plan(days):
    after=(now_ny()-__import__('datetime').timedelta(days=days)).astimezone(
        __import__('zoneinfo').ZoneInfo('UTC')
    ).isoformat()
    orders=getj(
        paper_api_url('/orders'),ah(),
        {'status':'all','after':after,'direction':'asc','limit':500},timeout=30,
    )
    if not isinstance(orders,list):
        raise RuntimeError('Alpaca returned an invalid order list')
    return broker_ledger_repair_plan(orders)


def fingerprint(plan):
    raw=json.dumps(plan,sort_keys=True,separators=(',',':'),default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days',type=int,default=30)
    parser.add_argument(
        '--apply',metavar='FINGERPRINT',
        help='apply only when this matches the fingerprint from a reviewed dry run',
    )
    args=parser.parse_args()
    plan=load_plan(max(1,min(args.days,90)))
    digest=fingerprint(plan)
    print(json.dumps({'fingerprint':digest,'actions':len(plan),'plan':plan},indent=2,default=str))
    if not args.apply:
        print(f'DRY RUN: re-run with --apply {digest} after reviewing every action')
        return
    if args.apply!=digest:
        raise SystemExit(f'refusing changed plan: expected {args.apply}, current {digest}')
    backup=backup_db('pre-ledger-repair')
    if not backup:
        raise SystemExit('refusing repair because the online backup failed')
    result=apply_broker_ledger_repair(plan)
    print(json.dumps({'backup':backup,**result},indent=2))


if __name__=='__main__':
    main()
