"""
Krok 0 – test prihlásenia do Gmailu (LEN NA ČÍTANIE).

Skript:
  - prihlási sa cez OAuth s oprávnením gmail.readonly (nič nemôže poslať ani zmazať),
  - vypíše, pod akým účtom je prihlásený,
  - vypíše max. 20 mailov s PDF prílohou za posledných 60 dní (len odosielateľ, dátum, predmet).

Nič nesťahuje a nič neukladá okrem prihlasovacieho tokenu do secrets/token.json.
"""
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

BASE = Path(__file__).resolve().parent
SECRETS = BASE / "secrets"
CREDENTIALS = SECRETS / "credentials.json"
TOKEN = SECRETS / "token.json"


def get_service():
    if not CREDENTIALS.exists():
        sys.exit(f"Chýba {CREDENTIALS} – stiahni OAuth klienta z Google Cloud (pozri návod).")

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json())
        os.chmod(TOKEN, 0o600)

    # Poistka: token nesmie mať žiadne iné oprávnenie než read-only.
    granted = set(creds.scopes or SCOPES)
    if granted - set(SCOPES):
        sys.exit(f"Token má navyše oprávnenia {granted - set(SCOPES)} – zmaž secrets/token.json a prihlás sa znova.")

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def main():
    svc = get_service()
    profile = svc.users().getProfile(userId="me").execute()
    print(f"\n✅ Prihlásený ako: {profile['emailAddress']} (len čítanie)\n")

    query = "has:attachment filename:pdf newer_than:60d"
    res = svc.users().messages().list(userId="me", q=query, maxResults=20).execute()
    msgs = res.get("messages", [])
    print(f"Mailov s PDF prílohou za 60 dní (max 20): {len(msgs)}\n")

    for m in msgs:
        meta = svc.users().messages().get(
            userId="me", id=m["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        h = {x["name"]: x["value"] for x in meta["payload"].get("headers", [])}
        print(f"- {h.get('Date', '')[:25]:25} | {h.get('From', '')[:40]:40} | {h.get('Subject', '')[:60]}")


if __name__ == "__main__":
    main()
