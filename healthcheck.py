#!/usr/bin/env python3
"""Exit non-zero when the trading runner heartbeat is stale."""
import json
import os

from app import runner_health


def main():
    max_age=float(os.environ.get('CEG_HEARTBEAT_MAX_AGE','90'))
    result=runner_health(max_age)
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['ok'] else 1)


if __name__=='__main__':
    main()
