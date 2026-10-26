#!/bin/bash
# Synchronisation git du depot de dossiers (a lancer chaque minute : cron ou minuteur systemd).
# Designed to NEVER silently fail: on conflict, sets a sentinel file
# that any agent can detect at session start.

set -Eeuo pipefail
export GIT_TERMINAL_PROMPT=0

ENGINE="$(cd "$(dirname "$0")" && pwd)"           # dossier scripts/ de ce depot
REPO="${DOSSIERS_DIR:-$(cd "$ENGINE/.." && pwd)}"   # le depot de VOS dossiers (topics/, journal/, MEMORY.md)
export DOSSIERS_DIR="$REPO"
STATE="${DOSSIERS_STATE:-$HOME/.local/state/dossiers-engine}"   # journaux et etat de la synchro (hors depot)
PYTHON="${DOSSIERS_PYTHON:-python3}"       # interpreteur qui a PyYAML ; pour le projecteur : celui qui a les bibliotheques Google
LOCK_FILE="$STATE/sync.lock"
SENTINEL_BROKEN="$REPO/.sync_broken"
ERROR_LOG="$STATE/sync-errors.log"

mkdir -p "$STATE"

# Single-writer constraint via flock (advisory lock)
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  # another sync already running, that's fine
  exit 0
fi

cd "$REPO"

fail() {
  local reason="$1"
  local head
  head=$(git rev-parse HEAD 2>/dev/null || echo "?")
  local timestamp
  timestamp=$(date -Is)
  {
    echo "[$timestamp] SYNC BROKEN"
    echo "  reason: $reason"
    echo "  HEAD: $head"
    echo "  ahead/behind: $(git rev-list --left-right --count main...origin/main 2>/dev/null || echo '?/?')"
    echo "  git status:"
    git status -s 2>&1 | sed 's/^/    /'
    echo "---"
  } | tee -a "$ERROR_LOG"
  cat > "$SENTINEL_BROKEN" <<EOF
$timestamp
$reason

HEAD: $head
Voir $ERROR_LOG pour le detail.
Resolution : suivre la procedure dans scripts/sync.sh:fail() ou demander a un agent humain.
EOF
  exit 1
}

trap 'fail "unexpected failure at line $LINENO"' ERR

# 1) commit any local working-tree changes (atomic in this step)
git add -A
if ! git diff --cached --quiet; then
  git commit -m "sync: $(date -Is)" >/dev/null
fi

# 2) fetch remote
git fetch origin main >/dev/null 2>&1 || fail "fetch failed"

LOCAL=$(git rev-parse main)
REMOTE=$(git rev-parse origin/main)
BASE=$(git merge-base main origin/main 2>/dev/null || echo "")

if [ "$LOCAL" = "$REMOTE" ]; then
  : # already in sync
elif [ "$LOCAL" = "$BASE" ]; then
  # local is strictly behind: fast-forward
  git pull --ff-only origin main >/dev/null 2>&1 || fail "fast-forward pull failed"
elif [ "$REMOTE" = "$BASE" ]; then
  : # local ahead, we will push at the end
else
  # diverged: try rebase first (clean linear history)
  if git pull --rebase --autostash origin main >/dev/null 2>&1; then
    : # rebase succeeded
  else
    git rebase --abort 2>/dev/null || true
    # try a regular merge (3-way)
    if git merge --no-edit origin/main >/dev/null 2>&1; then
      : # merge succeeded
    else
      git merge --abort 2>/dev/null || true
      # Both auto strategies failed -> DO NOT silently abort like before.
      # Set sentinel and bail. Resolution is manual (human or smart agent).
      fail "diverged & both rebase+merge auto-resolve failed (local=$LOCAL remote=$REMOTE)"
    fi
  fi
fi

# 4) un seul format d'en-tete (lisible par Obsidian) : remet a plat ce qu'un agent
# aurait ecrit autrement (bloc metadata: de l'outil memoire, liens mal ecrits).
"$PYTHON" "$ENGINE/normaliser.py" --quiet >/dev/null 2>&1 || true

# regenerate index
"$PYTHON" "$ENGINE/gen-index.py" >/dev/null 2>&1 || fail "memory index generation failed"

# 5) projecteur : ecrit en retour les pointeurs [task:ID] / [cal:ID]. Active seulement si DOSSIERS_PROJECTEUR_PYTHON
# est defini (interpreteur avec les bibliotheques Google, voir README). Rythme : au plus une fois toutes les 9 min
# sous systemd/cron (variable INVOCATION_ID ou DOSSIERS_CRON=1) ; un lancement a la main projette toujours.
PROJ_STAMP="$STATE/projecteur.stamp"
if [ -n "${DOSSIERS_PROJECTEUR_PYTHON:-}" ] && [ -x "$DOSSIERS_PROJECTEUR_PYTHON" ] && { { [ -z "${INVOCATION_ID:-}" ] && [ "${DOSSIERS_CRON:-0}" != 1 ]; } || [ ! -f "$PROJ_STAMP" ] || [ $(( $(date +%s) - $(stat -c %Y "$PROJ_STAMP") )) -ge 540 ]; }; then
  touch "$PROJ_STAMP"
  "$DOSSIERS_PROJECTEUR_PYTHON" "$ENGINE/projector/project.py" >> "$REPO/.projector.log" 2>&1 || true
fi

# 6) commit index + writebacks and push
git add -A
if ! git diff --cached --quiet; then
  git commit -m "sync: index+project" >/dev/null 2>&1
fi

# 7) push — retry once after a fresh fetch+rebase to handle race with concurrent laptop push
if ! git push origin main >/dev/null 2>&1; then
  git fetch origin main >/dev/null 2>&1 || true
  if git pull --rebase --autostash origin main >/dev/null 2>&1; then
    git push origin main >/dev/null 2>&1 || fail "push failed after rebase-retry"
  else
    git rebase --abort 2>/dev/null || true
    fail "push failed, retry rebase also failed"
  fi
fi

# Mark success only after the complete Git round trip.
rm -f "$SENTINEL_BROKEN"
date -Is > "$STATE/sync.success"
