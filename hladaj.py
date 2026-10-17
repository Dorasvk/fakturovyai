"""
Ľubovoľné vyhľadávanie v Gmaile (LEN ČÍTANIE) – vrátane Spamu a Koša.

Použitie:
    python hladaj.py "from:(openai OR anthropic OR stripe) newer_than:120d"
    python hladaj.py "claude receipt"
Zápis dotazu je rovnaký ako vo vyhľadávaní v Gmaile.
"""
import sys

from gmail_auth import get_service, vykonaj


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dotaz = " ".join(sys.argv[1:])
    svc = get_service()
    res = vykonaj(svc.users().messages().list(
        userId="me", q=dotaz, maxResults=30, includeSpamTrash=True))
    msgs = res.get("messages", [])
    print(f"\nDotaz: {dotaz}\nNájdených: {len(msgs)}{'+' if res.get('nextPageToken') else ''}\n")
    for m in msgs:
        P = "filename"
        msg = vykonaj(svc.users().messages().get(
            userId="me", id=m["id"], format="full",
            fields=f"labelIds,payload(headers,{P},parts({P},parts({P},parts({P}))))"))
        h = {x["name"].lower(): x["value"] for x in msg["payload"].get("headers", [])}
        prilohy, st = [], [msg["payload"]]
        while st:
            p = st.pop()
            if p.get("filename"):
                prilohy.append(p["filename"])
            st += p.get("parts", [])
        miesto = ",".join(l for l in msg.get("labelIds", []) if l in ("SPAM", "TRASH", "INBOX", "SENT")) or "archív"
        print(f"- {h.get('date', '')[:16]:16} [{miesto}] {h.get('from', '')[:45]:45} | {h.get('subject', '')[:55]}")
        if prilohy:
            print(f"    príloha: {', '.join(prilohy)[:110]}")


if __name__ == "__main__":
    main()
