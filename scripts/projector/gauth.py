"""Scoped Google auth for the dossier projector (Google Tasks + Calendar only).

The token file is produced once by `autoriser.py` (OAuth "desktop app" flow) and refreshed here.
Path: $DOSSIERS_GOOGLE_TOKEN, default ~/.config/dossiers-engine/token.json.
"""
import os

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN = os.environ.get("DOSSIERS_GOOGLE_TOKEN", os.path.expanduser("~/.config/dossiers-engine/token.json"))


def _creds():
    c = Credentials.from_authorized_user_file(TOKEN)
    if not c.valid:
        c.refresh(google.auth.transport.requests.Request())
        with open(TOKEN, "w", encoding="utf-8") as f:
            f.write(c.to_json())
        os.chmod(TOKEN, 0o600)
    return c


def tasks_service():
    return build("tasks", "v1", credentials=_creds(), cache_discovery=False)


def calendar_service():
    return build("calendar", "v3", credentials=_creds(), cache_discovery=False)
