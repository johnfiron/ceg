# ASH Terminal V10

Phone-first Flask **paper** desk. One UI file (`static/index.html`) plus `app.py`. Orders stay on the Alpaca paper API. Do not point this at live.

Open http://127.0.0.1:8765

## What it is

- Session clock and plain-language explain on Home
- Fifteen models: 3:45 overnight (CEG, VCT, XED, …) and midday sleeves (OPN, OSF, ORB, VRC, MVR)
- Replay with directional hit rate — not historical option P&L
- Lab: shadow book, debrief, snapshots, research metrics
- Title door: flakes or candles × white / market / pink. Identity default is **flakes + white**. Path-drawn A is shipped; do not rebuild it.

## Environments and safety

The default environment is `development`. It uses `config.development.json` and
`data/development/arena.db`; production uses its own config and data paths. All
examples set `broker_orders_enabled` to `false`, and missing or malformed values
also fail closed. Never commit environment config files or `data/`.

The web server and trading runner are separate processes. Importing `app.py`
initializes the schema but never starts trading. Broker order client IDs are
deterministic, and the runner audits recent Alpaca paper orders and positions
before its first evaluation cycle.

### WSL / Linux

```bash
bash start_wsl.sh
```

`start_wsl.sh` creates a safe `config.development.json` if missing and a venv at
`~/.venvs/ceg` (Linux disk — not `/mnt/c`). Override with `CEG_VENV`. It starts
the web and runner separately and stops both if either process fails.

### Termux

```bash
bash setup_termux.sh
bash start.sh
```

Stop with Ctrl-C on the start script. Do not `pkill -f "python app.py"` — that can
kill a Cursor agent attached to the same process name.

Dashboard on this device: http://127.0.0.1:8765  
LAN URL is printed by the start script when a non-loopback address exists.

The health endpoint is `GET /api/health`. It returns HTTP 503 when the runner
heartbeat is missing or older than 90 seconds, even if Flask itself is healthy.
The same check is available from `python healthcheck.py`.

## Production deployment

Production runs from `/opt/ash/current`, stores its SQLite database and backups
under `/var/lib/ash`, reads `/etc/ash/config.production.json`, and logs to the
persistent system journal. Two systemd services isolate the dashboard from the
trading runner. The runner uses systemd's watchdog, so a stale heartbeat causes
an automatic restart. The supplied web unit uses one Gunicorn worker so the web
and runner can coexist on a small VM; increase it only after checking memory.

On the server, clone the repository and install once:

```bash
sudo mkdir -p /opt/ash
sudo git clone YOUR_REPOSITORY_URL /opt/ash/repo
cd /opt/ash/repo
sudo bash deploy/install-server.sh
```

Then edit `/etc/ash/config.production.json`. Keep orders disabled through the
first production smoke test. Enable them only by setting the JSON value to the
literal `true`, then restart the runner:

```bash
sudo systemctl restart ash-runner.service
sudo systemctl status ash.target ash-web.service ash-runner.service
curl -f http://127.0.0.1:8765/api/health
sudo journalctl -u ash-runner -u ash-web -f
```

`ash-deploy.timer` polls `origin/main`. A new commit is checked out into an
immutable release directory, dependencies and safety tests run, and only then is
`/opt/ash/current` switched and the services restarted. Failed tests leave the
previous release running. Development happens on `dev`; promote only a tested
commit to `main`.

Useful checks:

```bash
python -m unittest discover -s tests -v
bash -n start.sh start_wsl.sh deploy/deploy-main.sh deploy/install-server.sh
```

## Replay

GREEN / RED / GRAY on replay labels mean directional outcome from 3:45 to the next-session open, not “signal fired”:

- CALL worked = next open > 3:45 underlying price
- PUT worked = next open < 3:45 underlying price

This is a directional underlying proxy. Replay also shows signal count, worked, missed, and hit rate.

## Title settings

Settings → Intro: **matter** and **color** are independent. They apply on the **next** launch. Fingerprint waits for ENTER after the A is built; AUTO is the timed door. Laptop `?record=1` can bake a denser webm into `static/` for the phone. Only `intro-flakes-white.webm` ships in git; other costumes fall back to the live canvas.

## Agent notes

Visual contract: `docs/ui-rulebook.md` and `.cursor/skills/ash-*`. Title engine and desk type/phone contract are shipped. Do not start another identity research pass, 26-letter alphabet, or WebGL.
