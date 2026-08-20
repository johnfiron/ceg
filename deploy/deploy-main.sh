#!/usr/bin/env bash
set -euo pipefail

ASH_ROOT=/opt/ash
ASH_REPO="$ASH_ROOT/repo"
ASH_RELEASES="$ASH_ROOT/releases"
ASH_CURRENT="$ASH_ROOT/current"
ASH_VENV="$ASH_ROOT/venv"
RUNNER_MARKER=/var/lib/ash/pending-runner-release

web_release() {
  curl -fsS http://127.0.0.1:8765/api/status 2>/dev/null |
    "$ASH_VENV/bin/python" -c 'import json,sys; print(json.load(sys.stdin).get("release") or "")' 2>/dev/null
}

wait_for_web_release() {
  local wanted=$1
  for _ in $(seq 1 45); do
    [ "$(web_release || true)" = "$wanted" ] && return 0
    sleep 1
  done
  return 1
}

market_window_open() {
  "$ASH_VENV/bin/python" -c 'from datetime import datetime; from zoneinfo import ZoneInfo; n=datetime.now(ZoneInfo("America/New_York")); print("yes" if n.weekday()<5 and "09:25"<=n.strftime("%H:%M")<="16:10" else "no")' |
    grep -qx yes
}

git -C "$ASH_REPO" fetch --quiet origin main
commit=$(git -C "$ASH_REPO" rev-parse origin/main)
release="$ASH_RELEASES/$commit"
old_release=$(readlink -f "$ASH_CURRENT" 2>/dev/null || true)
old_commit=$(basename "$old_release" 2>/dev/null || true)
runner_pid=$(systemctl show ash-runner.service -p MainPID --value 2>/dev/null || true)
runner_release=''
if [ -n "$runner_pid" ] && [ "$runner_pid" != 0 ]; then
  runner_release=$(readlink -f "/proc/$runner_pid/cwd" 2>/dev/null || true)
fi
runner_commit=$(basename "$runner_release" 2>/dev/null || true)
isolation_migration=false
isolation_rollback_needed=false
migration_backup=
if ! id ash-runner >/dev/null 2>&1 || ! id ash-web >/dev/null 2>&1 || \
   [ "$(systemctl show ash-runner.service -p User --value 2>/dev/null || true)" = ash ]; then
  isolation_migration=true
fi

# The original preloaded Gunicorn master cannot load a different symlink target
# via HUP. Defer this one-time unit migration until the trading window is over;
# every later code-only release uses graceful worker replacement.
if systemctl show ash-web.service -p ExecStart --value 2>/dev/null | grep -q -- '--preload' || $isolation_migration; then
  if market_window_open; then
    echo "one-time process-isolation migration deferred until after 16:10 America/New_York"
    exit 0
  fi
  first_graceful_migration=true
else
  first_graceful_migration=false
fi

if [ "$old_release" = "$release" ] && [ "$(web_release || true)" = "$commit" ]; then
  exit 0
fi
if [ ! -d "$release" ]; then
  git -C "$ASH_REPO" worktree add --detach "$release" "$commit"
fi
if [ ! -x "$ASH_VENV/bin/python" ]; then
  python3 -m venv "$ASH_VENV"
fi
"$ASH_VENV/bin/python" -m pip install --quiet -r "$release/requirements.txt"
cd "$release"
CEG_ENV=test "$ASH_VENV/bin/python" -m unittest discover -s tests -v

if $isolation_migration; then
  migration_backup=$(mktemp -d /run/ash-isolation.XXXXXX)
  for unit in ash-web.service ash-runner.service; do
    if [ -f "/etc/systemd/system/$unit" ]; then
      cp -a "/etc/systemd/system/$unit" "$migration_backup/$unit"
    fi
  done
  if [ -f /etc/systemd/system/ash-web.service.d/paper-orders.conf ]; then
    cp -a /etc/systemd/system/ash-web.service.d/paper-orders.conf "$migration_backup/paper-orders.conf"
  fi
  isolation_rollback_needed=true
  rollback_isolation() {
    local rc=$?
    trap - EXIT
    if $isolation_rollback_needed; then
      echo "restoring pre-isolation ASH services after deployment failure" >&2
      if [ -n "$old_release" ] && [ -d "$old_release" ]; then ln -sfn "$old_release" "$ASH_CURRENT"; fi
      for unit in ash-web.service ash-runner.service; do
        if [ -f "$migration_backup/$unit" ]; then
          install -m 0644 "$migration_backup/$unit" "/etc/systemd/system/$unit"
        fi
      done
      if [ -f "$migration_backup/paper-orders.conf" ]; then
        install -d /etc/systemd/system/ash-web.service.d
        install -m 0644 "$migration_backup/paper-orders.conf" /etc/systemd/system/ash-web.service.d/paper-orders.conf
      fi
      if id ash >/dev/null 2>&1; then chown -R ash:ash /var/lib/ash; fi
      systemctl daemon-reload || true
      systemctl restart ash-runner.service ash-web.service || true
    fi
    exit "$rc"
  }
  trap rollback_isolation EXIT
  getent group ash-readers >/dev/null 2>&1 || groupadd --system ash-readers
  getent group ash-runner >/dev/null 2>&1 || groupadd --system ash-runner
  id ash-runner >/dev/null 2>&1 || useradd --system --gid ash-runner --home /var/lib/ash --shell /usr/sbin/nologin ash-runner
  id ash-web >/dev/null 2>&1 || useradd --system --gid ash-readers --home /nonexistent --shell /usr/sbin/nologin ash-web
  usermod -g ash-runner -a -G ash-readers ash-runner
  usermod -g ash-readers ash-web
  install -d -o ash-runner -g ash-readers -m 2750 /var/lib/ash
  install -d -o root -g root -m 0755 /etc/ash
  chown root:ash-runner /etc/ash/config.production.json
  chmod 0640 /etc/ash/config.production.json
  install -o root -g ash-web -m 0640 "$release/config.production.example.json" /etc/ash/config.web.json
  systemctl stop ash-runner.service
  chown -R ash-runner:ash-readers /var/lib/ash
  find /var/lib/ash -type d -exec chmod 2750 {} +
  find /var/lib/ash -type f -exec chmod 0640 {} +
  if [ -d /var/lib/ash/backups ]; then chmod 0700 /var/lib/ash/backups; fi
fi

# Install tested service definitions before activating the release. The web
# master stays alive; HUP starts the new worker before retiring the old one.
install -m 0644 "$release/deploy/systemd/ash-web.service" /etc/systemd/system/ash-web.service
install -m 0644 "$release/deploy/systemd/ash-runner.service" /etc/systemd/system/ash-runner.service
install -m 0644 "$release/deploy/systemd/ash-runner-upgrade.service" /etc/systemd/system/ash-runner-upgrade.service
install -m 0644 "$release/deploy/systemd/ash-runner-upgrade.timer" /etc/systemd/system/ash-runner-upgrade.timer
rm -f /etc/systemd/system/ash-web.service.d/paper-orders.conf
install -m 0755 "$release/deploy/restart-pending-runner.sh" /usr/local/sbin/ash-restart-pending-runner
systemctl daemon-reload
systemctl enable --now ash-runner-upgrade.timer

ln -sfn "$release" "$ASH_CURRENT"
if $first_graceful_migration; then
  systemctl restart ash-web.service
elif systemctl is-active --quiet ash-web.service; then
  systemctl reload ash-web.service
else
  systemctl start ash-web.service
fi
if ! wait_for_web_release "$commit"; then
  if [ -n "$old_release" ] && [ -d "$old_release" ]; then
    ln -sfn "$old_release" "$ASH_CURRENT"
    systemctl reload-or-restart ash-web.service || true
  fi
  echo "new ASH web release failed its live health gate; rolled back" >&2
  exit 1
fi

# The stable systemd entry point is refreshed only after the release has
# passed its live web health gate. The running shell keeps its current script;
# the next timer invocation receives the tested deploy logic.
install -m 0755 "$release/deploy/deploy-main.sh" /usr/local/sbin/ash-deploy-main

runner_changed=true
if ! $isolation_migration && [ -n "$runner_commit" ] && git -C "$ASH_REPO" cat-file -e "$runner_commit^{commit}" 2>/dev/null; then
  if git -C "$ASH_REPO" diff --quiet "$runner_commit" "$commit" -- app.py runner.py requirements.txt; then
    runner_changed=false
  fi
fi
if $runner_changed; then
  if market_window_open; then
    printf '%s\n' "$commit" > "$RUNNER_MARKER"
    echo "runner upgrade deferred until 16:15 America/New_York"
  else
    systemctl restart ash-runner.service
    rm -f "$RUNNER_MARKER"
  fi
fi

if $isolation_migration; then
  isolation_rollback_needed=false
  trap - EXIT
fi

mapfile -t old_releases < <(find "$ASH_RELEASES" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | cut -d' ' -f2- | tail -n +4)
for old_release in "${old_releases[@]}"; do
  [ "$old_release" = "$runner_release" ] && continue
  case "$old_release" in
    "$ASH_RELEASES"/*) git -C "$ASH_REPO" worktree remove --force "$old_release" ;;
    *) echo "Refusing to remove unexpected release path: $old_release" >&2; exit 1 ;;
  esac
done
git -C "$ASH_REPO" worktree prune
