# Prompt for the implementing agent

The desk type/phone pass is shipped. Do not redo rem type, tables, or nav.

**Startup animation** is a separate job. Use the directed brief:

**[docs/startup-animation-prompt.md](startup-animation-prompt.md)**

Copy everything below the horizontal rule in that file into a **new** agent chat. That agent needs no other context.

**ENTER cut** (title → setup/desk, after the movie) is a second job. Do not fold it into the movie agent:

**[docs/enter-cut-prompt.md](enter-cut-prompt.md)**

## Project reminders

- UI is one file: `static/index.html`
- Paper-only. Never print or commit `config.json`
- Restart: `kill -TERM` the `python app.py` PID, then `bash start_wsl.sh`. Never `pkill -f "python app.py"`
