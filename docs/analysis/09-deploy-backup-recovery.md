# 9. Deploy, backup, recovery

Observed Friday 21 August 2026, 20:40 America/New_York.

## Job

How a commit becomes `/opt/ash/current` without rewriting the book, and how the host comes back.

## Source of truth

- ASH: [`deploy/deploy-main.sh`](../../deploy/deploy-main.sh), [`deploy/install-server.sh`](../../deploy/install-server.sh), [`backup_db.py`](../../backup_db.py), [`deploy/backup-offsite.sh`](../../deploy/backup-offsite.sh), [`docs/cloud-recovery-runbook.md`](../cloud-recovery-runbook.md)
- Live: `ash-deploy.timer`, `ash-backup.timer`, `/opt/ash/releases`, `/var/lib/ash/backups`

## Invariants

- `ash-deploy.timer` polls `origin/main`. New commit → immutable worktree under `/opt/ash/releases/<sha>` → pip + `unittest` → switch `current` → health gate. Failed tests leave the previous release.
- Weekday 09:25–16:10: do not promote to `main`. If `main` moves anyway, runner upgrade is deferred (`pending-runner-release`) until 16:15; web may still move.
- Overlay copies into a release directory are not durable. The next main deploy replaces the tree.
- SQLite backups use the backup API, not a file copy of a live WAL db. Off-host: integrity_check, age, rclone. Disk snapshots are not a substitute.
- Newest three releases kept. Journald capped (install docs: 300 MB / 14 days).
- Do not start against an empty development file when the legacy book exists. Production book is `/var/lib/ash/arena.db` only.

## How it works now

Deploy compares `origin/main` to the current symlink and `/api/status` `release`. Same commit + matching web release → exit 0 (this is why a file overlay survived until main moved).

Runner restart is skipped during the market window when only web files change; `app.py` / `runner.py` / requirements changes set a pending marker instead.

**Live:** current and web release `4832132f2200d76588aa81dc6cb70f3f2530240e` (merge of PR #2). Runner release same. `ash-deploy.timer` and `ash-backup.timer` active. Ledger repair backup `arena_pre-ledger-repair_20260821_194626.db` under `/var/lib/ash/backups`.

The 21 Aug overlay (`install` of `app.py` onto `3307988`) was the failure mode this category exists to name. Commit `9d35e42` + merge to main + timer install is the durable path.

## Tests and gaps

Deploy itself runs `unittest discover` on the new tree before switching. There is no unit test that the timer refuses an overlay. Recovery is a runbook plus `deploy/verify-ash-restore.sh`.

FamilyVault deploys are a separate release path (`/opt/familyvault-current`, `/var/www/familyvault-current`). An ASH-only main push does not refresh vault KPIs.

## Drift, gaps, next question

- **Drift:** live `ash-runner` `CEG_ALLOW_BROKER_ORDERS=true` vs git unit `false`. A unit-file reinstall can disarm the runner.
- **Gap:** FamilyVault Trading Lab flag is a build-time Vite env. ASH deploy will not save it.
- **Next question:** should `install-server.sh` treat runner interlock as a host drop-in (`/etc/systemd/system/ash-runner.service.d/orders.conf`) so git can stay fail-closed while production stays armed?

Points at: [1](01-process-and-authority.md), [10](10-evidence-and-ops.md), [2](02-ledger-and-pnl.md) (backups before repair).
