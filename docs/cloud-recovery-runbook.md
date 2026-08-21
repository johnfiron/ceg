# Cloud hardening and recovery runbook

## Observed production boundary

Read-only inventory on 2026-08-20 found one `familyvault` VM in
`us-east1-c`. Public ingress targets only the `http-server` and
`https-server` tags. SSH is allowed only from Google IAP
(`35.235.240.0/20`) through the `iap-ssh` tag. The public default SSH, RDP,
and ICMP rules are disabled; `deploy/gcloud-hardening.sh --apply` removes
those obsolete rules instead of relying on their disabled state.

The VM uses OS Login. Its service account has only logging, monitoring, and
resource-metadata writer roles and no Secret Manager role. Do not grant the
shared VM service account secret access. ASH runner credentials remain in the
root-managed host configuration and are unreadable by the web process.

## Approved GCloud change

Review first:

```bash
deploy/gcloud-hardening.sh --dry-run
```

During an approved maintenance change:

```bash
deploy/gcloud-hardening.sh --apply
```

The script removes obsolete public management rules and creates/attaches a
daily 03:00 UTC snapshot schedule with 14-day retention. It does not remove the
external address because Caddy must receive public 80/443 traffic.

## Off-host application backups

Disk snapshots are not a substitute for application-consistent backups.

FamilyVault:

- `pg_dump` streams directly into `age`; plaintext is not written to disk.
- The encrypted database and root-managed backend environment are uploaded
  through the backup service's isolated rclone configuration.
- Missing rclone/configuration or a remote size mismatch fails the unit.

ASH:

- `backup_db.py` uses SQLite's backup API.
- `deploy/backup-offsite.sh` runs `PRAGMA integrity_check`, encrypts the
  consistent database with `age`, uploads it through an isolated rclone
  configuration, and verifies remote size.
- Configure `/etc/ash/backup.env`, `/etc/ash/backup-recipient.txt`, and
  `/var/lib/ash/offsite/rclone.conf` before expecting the timer to succeed.

The age private identity must remain off the VM. Keep it in the designated
offline recovery custody; the server receives only the public recipient.

## Restore drill

At least quarterly and after a schema/storage migration:

1. Download a recent encrypted backup from the off-host remote.
2. On an isolated recovery workstation, run:

   ```bash
   deploy/verify-ash-restore.sh BACKUP.db.age AGE_IDENTITY
   ```

3. For FamilyVault, from its repository run:

   ```bash
   RESTORE_DATABASE=familyvault_restore_test \
     deploy/verify-restore.sh DATABASE.sql.age CONFIG.env.age AGE_IDENTITY
   ```

4. Record backup timestamp, object checksum/size, restore duration, row-count
   sanity checks, and result. Never point the verification script at production.
5. Delete the temporary restore database and decrypted temporary files; both
   scripts clean them on normal and error exits.

## Deployment verification and rollback

Before deployment, run both repositories' tests/builds and shell syntax checks.
After deployment:

```bash
deploy/smoke-security.sh https://YOUR_DOMAIN
```

Also verify loopback listeners, service users, active timers, and the most
recent backup result. ASH releases retain previous worktrees and roll the web
symlink back if the live release check fails. FamilyVault deployment must retain
the previous static/backend release until migrations and health checks pass;
database migrations require a tested restore point before execution.
