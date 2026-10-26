# dossiers-engine — a Markdown memory per subject, projected to Google Tasks, Calendar and your phone

One Markdown file per subject (`topics/<slug>.md`) in a git repository is the **single source of truth** for what you
and your AI assistant know about it: current state, dated journal, open actions, appointments, alarms and side notes.

- A **generated index** (`MEMORY.md`, built from the front-matter, with natural-name aliases) is loaded at the start of
  each assistant session, so "open the dossier about the street party" resolves without searching.
- A **projector** turns lines you write (`## Pending`, `## RDV`, `## Alarme`) into Google Tasks, Google Calendar events
  and phone alarms, and writes the IDs back into the file: idempotent, no duplicates.
- A **sync script** commits, normalises headers, regenerates the index, projects, and pushes, every minute if you want.
- Two **Claude Code skills** (`update-dossier`, `open-dossier`) write and read the dossiers.

This repository is the **engine only**. Your dossiers are personal: keep them in your own *private* repository and
never publish them. Fictional examples are in `examples/`.

> The scripts' messages, the skills and the dossier section names (`## État actuel`, `## RDV`…) are in French; the
> section names are part of the format the scripts parse. See `docs/methode.md` (French) for the method:
> the four registers of a dossier, notes as branches, bridges between dossiers, and the projection rules.

## What is in the box

| Path | Role |
| --- | --- |
| `scripts/gen-index.py` | Builds `MEMORY.md` from `topics/*.md` (slug, type, aliases, one-line summary). Warns past 40 KB. |
| `scripts/normaliser.py` | Keeps every header in one flat, Obsidian-readable format and fixes broken `[[links]]` (idempotent). |
| `scripts/verifier-journal.py` | Checks that splitting a long dossier into "state + journal" lost no line. |
| `scripts/projector/project.py` | Pending → Google Tasks, RDV → Google Calendar (visio links, external attendees skipped), Alarme → alarm command. |
| `scripts/projector/autoriser.py`, `gauth.py` | One-time Google OAuth ("desktop app" client) and token refresh. |
| `scripts/projector/ics-import.py` | Imports an `.ics` invitation (stdin) into Google Calendar (insert, update, cancel). |
| `scripts/sync.sh` | The sync loop: commit, fetch, rebase/merge, normalise, index, project, push; writes `.sync_broken` on a real conflict instead of failing silently. |
| `scripts/sync-watch/` | Phone notification (ntfy) when a sync has been failing for 15 minutes. systemd units included. |
| `scripts/ntfy-alarm.sh`, `alarme-ntfy.sh`, `ntfy-server/` | Self-hosted [ntfy](https://ntfy.sh) alarms that ring on the phone, with a silent heads-up 2 h before; docker-compose for the server. |
| `skills/` | `update-dossier` and `open-dossier` (Claude Code skills, French). |
| `examples/` | Three invented dossiers and a journal. |
| `tests/` | Tests on real files and a throw-away git repo; the projector talks to a fake Google that records calls. |

## Requirements

- Linux or macOS with `bash`, `git`, Python ≥ 3.10.
- `pip install PyYAML` for the index, the normaliser and the sync.
- For the projector: `pip install -r scripts/projector/requirements.txt` (Google API client, `icalendar`) and a Google
  Cloud project with the **Tasks** and **Calendar** APIs enabled and an OAuth client of type *Desktop app*.
- Optional: a [ntfy](https://docs.ntfy.sh) server and `curl` for phone alarms; [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
  for the two skills (a separate Anthropic product).

## Quick start

```bash
git clone <this repository> dossiers-engine && cd dossiers-engine
python3 -m pip install PyYAML
# 1. your private dossiers repository
mkdir -p ~/mes-dossiers/{topics,journal} && git -C ~/mes-dossiers init -b main
cp examples/topics/*.md ~/mes-dossiers/topics/ && cp examples/journal/*.md ~/mes-dossiers/journal/
export DOSSIERS_DIR=~/mes-dossiers
printf '.projector.log\n.sync_broken\n' > $DOSSIERS_DIR/.gitignore
# 2. index and dry-run of the projection (no Google account needed)
python3 scripts/gen-index.py                     # -> MEMORY.md
python3 scripts/projector/project.py --dry-run   # shows what would be created
# 3. tests
python3 -m unittest discover -s tests
```

### Projection to Google (once)

```bash
python3 -m pip install -r scripts/projector/requirements.txt
python3 scripts/projector/autoriser.py client_secret.json   # opens a browser, writes ~/.config/dossiers-engine/token.json
export DOSSIERS_TZ=Europe/Paris                              # time zone of the hours written in your dossiers (default UTC)
python3 scripts/projector/project.py                         # for real
```

Tasks are created only for dossiers that declare `tasklist: <list name>`; events go to the primary calendar, or to the
calendar named by `calendar: <calendarId>` in the front-matter. The token and the client secret are never committed
(see `.gitignore`).

### Sync loop and alarms

```bash
# remote required: git -C $DOSSIERS_DIR remote add origin <your private remote>
DOSSIERS_PROJECTEUR_PYTHON=$(which python3) bash scripts/sync.sh      # cron: * * * * * with DOSSIERS_CRON=1
cp scripts/ntfy.env.example ~/.config/dossiers-engine/ntfy.env       # edit URL, topic, token (chmod 600)
export DOSSIERS_ALARM_CMD="$PWD/scripts/alarme-ntfy.sh"              # the projector rings alarms through it
```

Settings (environment variables): `DOSSIERS_DIR` (your dossiers repository), `DOSSIERS_STATE` (logs and sync state,
default `~/.local/state/dossiers-engine`), `DOSSIERS_PYTHON`, `DOSSIERS_PROJECTEUR_PYTHON`, `DOSSIERS_TZ`,
`DOSSIERS_GOOGLE_TOKEN`, `DOSSIERS_ALARM_CMD`, `NTFY_ENV`, `ALARM_REGISTER`.
`ntfy-server/docker-compose.yml` runs a ntfy server behind your own HTTPS proxy.

### The skills

Copy `skills/update-dossier` and `skills/open-dossier` into `~/.claude/skills/`, and make `MEMORY.md` part of your
assistant's context (for Claude Code: import it from your `CLAUDE.md`). The skills assume the dossiers live in `$DOSSIERS_DIR`.

## Not included, on purpose

- Any real dossier. The method keeps health, family, money and work subjects in one place: that repository must stay private.
- Service-specific glue (a dashboard of links, a phone macro, a shared-drive client): not part of the engine.

## Licenses

- Code: Apache License 2.0 (`LICENSE`, `NOTICE`).
- Documentation, example dossiers and skills (`README.md`, `docs/`, `examples/`, `skills/`): CC BY 4.0 (`LICENSE-docs`).
- Third-party dependencies are installed from PyPI, not redistributed; see `NOTICE`. The ntfy server is a separate
  service (Apache-2.0 / GPL-2.0 dual license).
