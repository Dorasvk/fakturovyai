"""Spoločné prihlásenie do Gmailu – LEN NA ČÍTANIE (gmail.readonly)."""
import os
import sys
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE = Path(__file__).resolve().parent
CREDENTIALS = BASE / "secrets" / "credentials.json"
TOKEN = BASE / "secrets" / "token.json"


def _login():
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    return flow.run_local_server(port=0)


def get_service():
    if not CREDENTIALS.exists():
        sys.exit(f"Chýba {CREDENTIALS} – stiahni OAuth klienta z Google Cloud.")

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Režim Testing: prihlásenie vyprší po 7 dňoch -> prihlásime sa nanovo
                print("Prihlásenie vypršalo, otváram prehliadač na nové prihlásenie…")
                creds = _login()
        else:
            creds = _login()
        TOKEN.write_text(creds.to_json())
        os.chmod(TOKEN, 0o600)

    # Poistka: token nesmie mať žiadne iné oprávnenie než read-only
    extra = set(creds.scopes or SCOPES) - set(SCOPES)
    if extra:
        sys.exit(f"Token má navyše oprávnenia {extra} – zmaž secrets/token.json a prihlás sa znova.")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)
