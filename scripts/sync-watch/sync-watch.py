#!/usr/bin/env python3
"""Veille des synchronisations (dépôt de dossiers, skills… entre vos machines).

Une synchro en échec ne se voit nulle part si personne ne la regarde. Chaque machine publie l'état de sa synchro
dans un dossier commun (DOSSIERS_STATE, par défaut ~/.local/state/dossiers-engine) :
  <nom>.status.json   {"ok": true}  ou  {"ok": false, "error": "texte"}
  <nom>.error         fichier texte non vide = échec, son contenu est le motif
Si une synchro est en échec depuis plus de 15 min, une notification part sur le téléphone (ntfy, priorité 3), au plus
une fois toutes les 6 h par synchro. À lancer toutes les 5 min (sync-watch.timer ou cron).
Réglages ntfy : fichier NTFY_ENV (voir ../ntfy.env.example).
"""
import glob
import json
import os
import time
import urllib.request

D = os.environ.get("DOSSIERS_STATE", os.path.expanduser("~/.local/state/dossiers-engine"))
STATE = os.path.join(D, "sync-watch.json")
SEUIL, RAPPEL = 15 * 60, 6 * 3600


def env():
    e = {}
    for l in open(os.environ.get("NTFY_ENV", os.path.expanduser("~/.config/dossiers-engine/ntfy.env"))):
        if "=" in l and not l.lstrip().startswith("#"):
            k, v = l.strip().split("=", 1)
            e[k] = v.strip().strip('"')
    return e


def etats():
    out = {}
    for f in sorted(glob.glob(os.path.join(D, "*.status.json"))):
        nom = os.path.basename(f)[: -len(".status.json")]
        try:
            j = json.load(open(f, encoding="utf-8-sig"))
            out[nom] = None if j.get("ok") else (j.get("error") or "echec")
        except Exception as ex:
            out[nom] = "etat illisible: %s" % ex
    for f in sorted(glob.glob(os.path.join(D, "*.error"))):
        nom = os.path.basename(f)[: -len(".error")]
        txt = open(f).read().strip()
        out[nom] = txt or None
    return out


def notifier(titre, msg):
    e = env()
    req = urllib.request.Request(
        e["NTFY_URL"] + "/" + e["NTFY_TOPIC"], data=msg.encode(), method="POST",
        headers={"Authorization": "Bearer " + e["NTFY_TOKEN"], "Priority": "3",
                 "Tags": "warning", "Title": titre.encode("ascii", "ignore").decode()})
    urllib.request.urlopen(req, timeout=15)


def main():
    os.makedirs(D, exist_ok=True)
    st = json.load(open(STATE)) if os.path.exists(STATE) else {}
    now = time.time()
    for nom, err in etats().items():
        s = st.setdefault(nom, {})
        if not err:
            st[nom] = {}
            continue
        s.setdefault("depuis", now)
        if now - s["depuis"] >= SEUIL and now - s.get("notifie", 0) >= RAPPEL:
            minutes = int((now - s["depuis"]) // 60)
            notifier("Sync en echec : " + nom, "Depuis %d min. %s" % (minutes, err[:300]))
            s["notifie"] = now
    json.dump(st, open(STATE, "w"))


if __name__ == "__main__":
    main()
