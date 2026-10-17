"""
Krok 1 – PREHĽAD kandidátov na faktúry v Gmaile (nič nesťahuje, nič nemení).

Použitie:
    python 1_gmail_scan.py              # predchádzajúci mesiac (napr. v októbri = september)
    python 1_gmail_scan.py 2026-09      # konkrétny mesiac

Hľadá od 1. dňa zvoleného mesiaca až po dnešok (faktúry môžu prísť neskôr).
Výstup: vystup/scan_RRRR-MM.csv (otvoríš v Exceli/Numbers)
"""
import csv
import json
import sys
import time
from collections import Counter
from datetime import date, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from googleapiclient.errors import HttpError

import config
from gmail_auth import get_service
from skore import ohodnot

BASE = Path(__file__).resolve().parent


def obdobie_z_argumentu():
    if len(sys.argv) > 1:
        r, m = map(int, sys.argv[1].split("-"))
        return date(r, m, 1)
    prvy_tento = date.today().replace(day=1)
    return (prvy_tento - timedelta(days=1)).replace(day=1)


def zostav_dotaz(od: date, do: date) -> str:
    slova = " OR ".join(f'"{s}"' if " " in s else s for s in config.KLUCOVE_SLOVA)
    odos = " OR ".join(config.ZNAMI_ODOSIELATELIA)
    prilohy = " OR ".join(f"filename:{p}" for p in config.PRILOHY)
    return (
        f"after:{od:%Y/%m/%d} before:{do:%Y/%m/%d} "
        f"({prilohy} OR {slova} OR from:({odos}))"
    )


def vsetky_spravy(svc, dotaz):
    ids, token = [], None
    while True:
        res = vykonaj(svc.users().messages().list(
            userId="me", q=dotaz, pageToken=token, maxResults=500
        ))
        ids += [m["id"] for m in res.get("messages", [])]
        token = res.get("nextPageToken")
        if not token:
            return ids


def vykonaj(req, pokusov=8):
    """Spustí požiadavku; pri prekročení limitu počká a skúsi znova."""
    pauza = 5
    for _ in range(pokusov):
        try:
            return req.execute()
        except HttpError as e:
            if (e.resp.status in (403, 429) and "rate" in str(e).lower()) or e.resp.status in (500, 503):
                print(f"  ... limit Gmail API – čakám {pauza} s…")
                time.sleep(pauza)
                pauza = min(pauza * 2, 60)
                continue
            raise
    raise RuntimeError("Gmail API opakovane odmieta požiadavky, skús neskôr.")


def nazvy_priloh(payload):
    out, stack = [], [payload]
    while stack:
        p = stack.pop()
        if p.get("filename"):
            out.append(p["filename"])
        stack += p.get("parts", [])
    return out


def main():
    od = obdobie_z_argumentu()
    do = date.today() + timedelta(days=1)
    mesiac = f"{od:%Y-%m}"
    print(f"\nObdobie (DZP): {mesiac} | hľadám maily od {od} do {date.today()}\n")

    svc = get_service()
    dotaz = zostav_dotaz(od, do)
    ids = vsetky_spravy(svc, dotaz)
    print(f"Nájdených kandidátov: {len(ids)}\n")

    vystup = BASE / "vystup"
    vystup.mkdir(exist_ok=True)
    cache_subor = vystup / "cache_spravy.json"
    cache = json.loads(cache_subor.read_text()) if cache_subor.exists() else {}

    riadky = []
    for i, mid in enumerate(ids, 1):
        if mid in cache and "labelIds" in cache[mid]:
            msg = cache[mid]
        else:
            P = "filename,mimeType"
            msg = vykonaj(svc.users().messages().get(
                userId="me", id=mid, format="full",
                fields=f"id,labelIds,snippet,payload(headers,{P},parts({P},parts({P},parts({P}))))",
            ))
            cache[mid] = msg
            if i % 10 == 0:
                cache_subor.write_text(json.dumps(cache))
            time.sleep(0.3)
        h = {x["name"].lower(): x["value"] for x in msg["payload"].get("headers", [])}
        odosielatel = h.get("from", "")
        predmet = h.get("subject", "")
        try:
            datum = parsedate_to_datetime(h.get("date", "")).strftime("%Y-%m-%d")
        except Exception:
            datum = ""
        prilohy = nazvy_priloh(msg["payload"])
        skore, skupina, dovod = ohodnot(
            odosielatel, predmet, msg.get("snippet", ""), prilohy, set(msg.get("labelIds", []))
        )
        riadky.append({
            "skupina": skupina,
            "skore": skore,
            "datum": datum,
            "odosielatel": odosielatel,
            "domena": parseaddr(odosielatel)[1].split("@")[-1].lower(),
            "predmet": predmet,
            "prilohy": " | ".join(prilohy),
            "dovod": dovod,
            "ukazka": msg.get("snippet", "")[:150],
            "gmail_id": mid,
        })
        if i % 25 == 0:
            print(f"  … spracovaných {i}/{len(ids)}")

    cache_subor.write_text(json.dumps(cache))
    riadky.sort(key=lambda r: (-r["skore"], r["datum"]))
    subor = vystup / f"scan_{mesiac}.csv"
    with open(subor, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(riadky[0].keys()) if riadky else ["datum"], delimiter=";")
        w.writeheader()
        w.writerows(riadky)

    pocty = Counter(r["skupina"] for r in riadky)
    print("\nVýsledok:")
    for k in ["[#] výpis", "[+] faktúra", "[?] možno", "[-] šum"]:
        print(f"  {k:12} {pocty.get(k, 0):4}")
    print("\nFaktúry:")
    for r in riadky:
        if r["skupina"] == "[+] faktúra":
            print(f"  {r['datum']}  {r['domena'][:25]:25}  {r['predmet'][:60]}")
    print(f"\nTabuľka: {subor}")


if __name__ == "__main__":
    main()
