# ASH Terminal V10

Phone-first Flask **paper** desk. One UI file (`static/index.html`) plus `app.py`. Orders stay on the Alpaca paper API. Do not point this at live.

Open http://127.0.0.1:8765

## What it is

- Session clock and plain-language explain on Home
- Fifteen models: 3:45 overnight (CEG, VCT, XED, …) and midday sleeves (OPN, OSF, ORB, VRC, MVR)
- Replay with directional hit rate — not historical option P&L
- Lab: shadow book, debrief, snapshots, research metrics
- Title door: flakes or candles × white / market / pink. Identity default is **flakes + white**. Path-drawn A is shipped; do not rebuild it.

## Run

Copy the example config once. Leave keys empty to boot the UI. Add Alpaca paper (and optional FRED) keys when you want tape or paper orders. Never commit `config.json` or `data/`.

```bash
cp config.example.json config.json
```

### WSL / Linux

```bash
bash start_wsl.sh
```

`start_wsl.sh` creates `config.json` if missing and a venv at `~/.venvs/ceg` (Linux disk — not `/mnt/c`). Override with `CEG_VENV`.

### Termux

```bash
bash setup_termux.sh
bash start.sh
```

Stop with Ctrl-C on the start script, or `kill -TERM` on the `python app.py` PID. Do not `pkill -f "python app.py"` — that can kill a Cursor agent attached to the same process name.

Dashboard on this device: http://127.0.0.1:8765  
LAN URL is printed by the start script when a non-loopback address exists.

## Replay

GREEN / RED / GRAY on replay labels mean directional outcome from 3:45 to the next-session open, not “signal fired”:

- CALL worked = next open > 3:45 underlying price
- PUT worked = next open < 3:45 underlying price

This is a directional underlying proxy. Replay also shows signal count, worked, missed, and hit rate.

## Title settings

Settings → Intro: **matter** and **color** are independent. They apply on the **next** launch. Fingerprint waits for ENTER after the A is built; AUTO is the timed door. Laptop `?record=1` can bake a denser webm into `static/` for the phone. Only `intro-flakes-white.webm` ships in git; other costumes fall back to the live canvas.

## Agent notes

Visual contract: `docs/ui-rulebook.md` and `.cursor/skills/ash-*`. Title engine and desk type/phone contract are shipped. Do not start another identity research pass, 26-letter alphabet, or WebGL.
