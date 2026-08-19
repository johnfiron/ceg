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
id ash >/dev/null 2>&1 || useradd --system --home /var/lib/ash --shell /usr/sbin/nologin ash
install -d -o ash -g ash /var/lib/ash /etc/ash /opt/ash/releases
install -d /var/log/journal
if [ ! -f /etc/ash/config.production.json ]; then
  install -o ash -g ash -m 0600 /opt/ash/repo/config.production.example.json /etc/ash/config.production.json
fi
install -m 0644 /opt/ash/repo/deploy/systemd/ash.target /etc/systemd/system/ash.target
install -m 0644 /opt/ash/repo/deploy/systemd/ash-web.service /etc/systemd/system/ash-web.service
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
