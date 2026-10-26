#!/bin/bash
# ntfy-alarm : alarme qui sonne en boucle sur le telephone via un serveur ntfy (le votre : voir ntfy-server/).
# Usage : ntfy-alarm "YYYY-MM-DD HH:MM" "Titre" ["message"]   (heure du fuseau DOSSIERS_TZ, UTC par defaut)
#         ntfy-alarm now "Titre" ["message"]
#         ntfy-alarm cancel <id>          (annule une alarme programmee pas encore sonnee, et son pre-avis)
# Toute alarme datee est precedee d'un PRE-AVIS SILENCIEUX 2 h avant (priorite 2 : ni son ni vibration,
# visible dans le volet), publie sous l'id "<id>-pre" pour etre annule/decale avec l'alarme.
# Si l'alarme tombe dans moins de 2 h, le pre-avis part tout de suite (sauf "now").
# Chaque alarme est inscrite dans un registre JSONL (ALARM_REGISTER, par defaut ~/.local/share/dossiers-engine/alarms.jsonl).
# Reglages : fichier NTFY_ENV (par defaut ~/.config/dossiers-engine/ntfy.env) avec NTFY_URL, NTFY_TOPIC, NTFY_TOKEN
# (voir ntfy.env.example). Ce fichier ne se versionne jamais.
set -euo pipefail
. "${NTFY_ENV:-$HOME/.config/dossiers-engine/ntfy.env}"
REG="${ALARM_REGISTER:-$HOME/.local/share/dossiers-engine/alarms.jsonl}"
ZONE="${DOSSIERS_TZ:-UTC}"
mkdir -p "$(dirname "$REG")"
if [ "${1:-}" = cancel ]; then
  curl -sf -o /dev/null -w "annulee: %{http_code}\n" -X DELETE -H "Authorization: Bearer $NTFY_TOKEN" "$NTFY_URL/$NTFY_TOPIC/$2"
  curl -s -o /dev/null -X DELETE -H "Authorization: Bearer $NTFY_TOKEN" "$NTFY_URL/$NTFY_TOPIC/$2-pre" || true
  python3 -c 'import json,sys,time;print(json.dumps({"op":"cancel","id":sys.argv[1],"at":int(time.time())}))' "$2" >> "$REG"
  exit
fi
WHEN=$1; TITLE=$2; MSG=${3:-$2}
H=(); TS=$(date +%s)
if [ "$WHEN" != now ]; then
  TS=$(TZ=$ZONE date -d "$WHEN" +%s) || { echo "date invalide: $WHEN" >&2; exit 1; }
  [ "$TS" -gt "$(date +%s)" ] || { echo "date dans le passe: $WHEN" >&2; exit 1; }
  H=(-H "At: $TS")
fi
OUT=$(curl -sf -H "Authorization: Bearer $NTFY_TOKEN" -H "Title: $TITLE" -H "Priority: 5" -H "Tags: alarm_clock" "${H[@]}" -d "$MSG" "$NTFY_URL/$NTFY_TOPIC")
ID=$(printf '%s' "$OUT" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])') || { echo "reponse ntfy illisible : $OUT" >&2; exit 1; }
python3 -c 'import json,sys,time;print(json.dumps({"op":"create","id":sys.argv[1],"time":int(sys.argv[2]),"title":sys.argv[3],"msg":sys.argv[4],"source":"dossiers-engine (ntfy-alarm)","at":int(time.time())},ensure_ascii=False))' "$ID" "$TS" "$TITLE" "$MSG" >> "$REG"
PRE_AVANCE=7200
if [ "$WHEN" != now ]; then
  PRE=$((TS - PRE_AVANCE)); PH=()
  [ "$PRE" -gt "$(( $(date +%s) + 10 ))" ] && PH=(-H "At: $PRE")
  HHMM=$(TZ=$ZONE date -d @$TS +%H:%M)
  curl -sf -o /dev/null -H "Authorization: Bearer $NTFY_TOKEN" -H "Title: A $HHMM : $TITLE" -H "Priority: 2" -H "Tags: hourglass" "${PH[@]}" \
    -d "Alarme a $HHMM : $MSG" "$NTFY_URL/$NTFY_TOPIC/$ID-pre" && echo "pre-avis silencieux: $(TZ=$ZONE date -d @$(( PRE > $(date +%s) ? PRE : $(date +%s) )) '+%Y-%m-%d %H:%M')"
fi
echo "\"id\":\"$ID\" \"time\":$TS ($(TZ=$ZONE date -d @$TS '+%Y-%m-%d %H:%M'))"
