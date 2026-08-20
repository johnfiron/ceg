#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run as root: sudo bash deploy/install-server.sh"
  exit 1
fi
if [ ! -d /opt/ash/repo/.git ]; then
  echo "Clone this repository to /opt/ash/repo before running the installer."
  exit 1
fi
getent group ash-readers >/dev/null 2>&1 || groupadd --system ash-readers
getent group ash-runner >/dev/null 2>&1 || groupadd --system ash-runner
id ash-runner >/dev/null 2>&1 || useradd --system --gid ash-runner --home /var/lib/ash --shell /usr/sbin/nologin ash-runner
id ash-web >/dev/null 2>&1 || useradd --system --gid ash-readers --home /nonexistent --shell /usr/sbin/nologin ash-web
usermod -g ash-runner -a -G ash-readers ash-runner
usermod -g ash-readers ash-web
install -d -o ash-runner -g ash-readers -m 2750 /var/lib/ash
install -d -o root -g root -m 0755 /etc/ash /opt/ash/releases
install -d /var/log/journal
if [ ! -f /etc/ash/config.production.json ]; then
  install -o root -g ash-runner -m 0640 /opt/ash/repo/config.production.example.json /etc/ash/config.production.json
fi
chown root:ash-runner /etc/ash/config.production.json
chmod 0640 /etc/ash/config.production.json
install -o root -g ash-web -m 0640 /opt/ash/repo/config.production.example.json /etc/ash/config.web.json
if command -v jq >/dev/null; then
  tmp_web=$(mktemp /etc/ash/config.web.json.XXXXXX)
  jq 'del(.alpaca_key,.alpaca_secret,.fred_key,.ntfy_url) | .broker_orders_enabled=false | .keys_ok=false' \
    /etc/ash/config.web.json > "$tmp_web"
  chown root:ash-web "$tmp_web"
  chmod 0640 "$tmp_web"
  mv -f "$tmp_web" /etc/ash/config.web.json
fi
# Migrate the original single-user installation without exposing runner secrets.
chown -R ash-runner:ash-readers /var/lib/ash
find /var/lib/ash -type d -exec chmod 2750 {} +
find /var/lib/ash -type f -exec chmod 0640 {} +
if [ -d /var/lib/ash/backups ]; then chmod 0700 /var/lib/ash/backups; fi
install -m 0644 /opt/ash/repo/deploy/systemd/ash.target /etc/systemd/system/ash.target
install -m 0644 /opt/ash/repo/deploy/systemd/ash-web.service /etc/systemd/system/ash-web.service
rm -f /etc/systemd/system/ash-web.service.d/paper-orders.conf
install -m 0644 /opt/ash/repo/deploy/systemd/ash-runner.service /etc/systemd/system/ash-runner.service
install -m 0644 /opt/ash/repo/deploy/systemd/ash-deploy.service /etc/systemd/system/ash-deploy.service
install -m 0644 /opt/ash/repo/deploy/systemd/ash-deploy.timer /etc/systemd/system/ash-deploy.timer
install -m 0644 /opt/ash/repo/deploy/systemd/ash-backup.service /etc/systemd/system/ash-backup.service
install -m 0644 /opt/ash/repo/deploy/systemd/ash-backup.timer /etc/systemd/system/ash-backup.timer
install -m 0644 /opt/ash/repo/deploy/systemd/ash-runner-upgrade.service /etc/systemd/system/ash-runner-upgrade.service
install -m 0644 /opt/ash/repo/deploy/systemd/ash-runner-upgrade.timer /etc/systemd/system/ash-runner-upgrade.timer
install -m 0755 /opt/ash/repo/deploy/deploy-main.sh /usr/local/sbin/ash-deploy-main
install -m 0755 /opt/ash/repo/deploy/restart-pending-runner.sh /usr/local/sbin/ash-restart-pending-runner
install -d /etc/systemd/journald.conf.d
install -m 0644 /opt/ash/repo/deploy/journald/ash-retention.conf /etc/systemd/journald.conf.d/ash-retention.conf
systemctl daemon-reload
/usr/local/sbin/ash-deploy-main
systemctl enable --now ash.target ash-deploy.timer ash-backup.timer ash-runner-upgrade.timer
systemctl restart systemd-journald.service
echo "Installed. Edit /etc/ash/config.production.json, then restart ash-runner.service."
