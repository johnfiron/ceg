#!/usr/bin/env bash
set -euo pipefail

ASH_ROOT=/opt/ash
ASH_REPO="$ASH_ROOT/repo"
ASH_RELEASES="$ASH_ROOT/releases"
ASH_CURRENT="$ASH_ROOT/current"
ASH_VENV="$ASH_ROOT/venv"

git -C "$ASH_REPO" fetch --quiet origin main
commit=$(git -C "$ASH_REPO" rev-parse origin/main)
release="$ASH_RELEASES/$commit"
if [ "$(readlink -f "$ASH_CURRENT" 2>/dev/null || true)" = "$release" ]; then
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
ln -sfn "$release" "$ASH_CURRENT"
systemctl restart ash.target
