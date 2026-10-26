#!/bin/bash
# Adaptateur : traduit l'appel du projecteur (DOSSIERS_ALARM_CMD) vers ntfy-alarm.sh.
#   alarme-ntfy.sh --hour 7 --minute 15 --label "Titre" [--days 2,3] [--silent] [--no-vibrate]
# ntfy ne pose qu'une alarme ponctuelle : le jour meme a l'heure donnee. --days (recurrence), --silent et
# --no-vibrate sont refuses (code 3) pour que le projecteur laisse la ligne en attente au lieu de mentir.
set -euo pipefail
HOUR=; MIN=; LABEL=
while [ $# -gt 0 ]; do case "$1" in
  --hour) HOUR=$2; shift;; --minute) MIN=$2; shift;; --label) LABEL=$2; shift;;
  --days|--silent|--no-vibrate) echo "option non geree par ntfy : $1" >&2; exit 3;;
esac; shift; done
[ -n "$HOUR" ] && [ -n "$MIN" ] && [ -n "$LABEL" ] || { echo "usage: --hour H --minute M --label TEXTE" >&2; exit 2; }
ZONE="${DOSSIERS_TZ:-UTC}"
exec "$(dirname "$0")/ntfy-alarm.sh" "$(TZ=$ZONE date +%F) $(printf '%02d:%02d' "$HOUR" "$MIN")" "$LABEL"
