#!/usr/bin/env python3
"""Autorise le projecteur auprès de Google (une seule fois, sur une machine avec un navigateur).

  autoriser.py client_secret.json

`client_secret.json` : un identifiant OAuth de type « application de bureau », créé dans la console Google Cloud
(API Google Tasks et Google Calendar activées). Écrit le jeton dans $DOSSIERS_GOOGLE_TOKEN
(par défaut ~/.config/dossiers-engine/token.json), en lecture seule pour vous (chmod 600).
Portées demandées : Tasks et Calendar, rien d'autre. Ne versionnez jamais ces deux fichiers.
"""
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/tasks", "https://www.googleapis.com/auth/calendar"]
TOKEN = os.environ.get("DOSSIERS_GOOGLE_TOKEN", os.path.expanduser("~/.config/dossiers-engine/token.json"))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    creds = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES).run_local_server(port=0)
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
    with open(TOKEN, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    os.chmod(TOKEN, 0o600)
    print("jeton écrit :", TOKEN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
