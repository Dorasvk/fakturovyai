"""
Krok 2 – stiahne faktúry ([+] + [?]) a výpisy ([#]) podľa tabuľky z kroku 1.

Použitie:
    python 2_stiahni.py            # predchádzajúci mesiac
    python 2_stiahni.py 2026-09    # konkrétny mesiac

- prílohy PDF/ISDOC/XML uloží, ZIP rozbalí (aj AES – heslá v secrets/zip_hesla.txt, jedno na riadok)
- preskočí obchodné podmienky, VOP, obrázky a pod.
- mail bez prílohy (Apple, Bolt…) uloží ako HTML (na tlač sa prevedie v kroku tlače)
- duplicity podľa obsahu (SHA-256) uloží len raz
Výstup: vystup/RRRR-MM/faktury/, vystup/RRRR-MM/vypisy/, vystup/RRRR-MM/stiahnute.csv
Gmail: LEN ČÍTANIE.
"""
import base64
import csv
import hashlib
import io
import re
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import config
from gmail_auth import get_service, vykonaj
from skore import BALAST_PRILOHA

BASE = Path(__file__).resolve().parent
UZITOCNE = {"pdf", "isdoc", "xml"}
HESLA_SUBOR = BASE / "secrets" / "zip_hesla.txt"


def povoleny(domena, meno):
    """Ak má dodávateľ v config.LEN_SUBORY pravidlo, berieme len súbory, ktoré mu vyhovujú."""
    for dom, vzor in getattr(config, "LEN_SUBORY", {}).items():
        if dom in domena:
            return re.search(vzor, meno, re.I) is not None
    return True


def mesiac_z_argumentu():
    if len(sys.argv) > 1:
        return sys.argv[1]
    prvy = date.today().replace(day=1)
    return f"{(prvy - timedelta(days=1)):%Y-%m}"


def bezpecne_meno(s, max_len=120):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s).strip(" ._")
    return s[:max_len] or "subor"


def pripona(meno):
    return meno.rsplit(".", 1)[-1].lower() if "." in meno else ""


def b64(data):
    return base64.urlsafe_b64decode(data.encode() if isinstance(data, str) else data)


def casti(payload):
    stack = [payload]
    while stack:
        p = stack.pop()
        yield p
        stack += p.get("parts", [])


def nacitaj_hesla():
    if not HESLA_SUBOR.exists():
        return []
    return [r.strip() for r in HESLA_SUBOR.read_text().splitlines() if r.strip()]


def rozbal_zip(data, hesla):
    """Vráti (zoznam (meno, bytes), poznamka)."""
    vysledok = []
    try:
        import pyzipper
        z = pyzipper.AESZipFile(io.BytesIO(data))
    except ImportError:
        z = zipfile.ZipFile(io.BytesIO(data))
    sifrovany = any(i.flag_bits & 0x1 for i in z.infolist())
    kandidati = [None] + [h.encode() for h in hesla] if sifrovany else [None]
    for heslo in kandidati:
        try:
            if heslo:
                z.setpassword(heslo)
            for info in z.infolist():
                if info.is_dir():
                    continue
                meno = Path(info.filename).name
                if pripona(meno) in UZITOCNE:
                    vysledok.append((meno, z.read(info)))
            return vysledok, ("rozbalený s heslom" if heslo else "rozbalený")
        except (RuntimeError, zipfile.BadZipFile) as e:
            vysledok = []
            if "password" not in str(e).lower() and "encrypted" not in str(e).lower():
                return [], f"chyba ZIP: {e}"
    return [], "ZIP je zaheslovaný – heslo neznáme (doplň do secrets/zip_hesla.txt)"


def telo_mailu(svc, mid, payload):
    html = txt = None
    for p in casti(payload):
        mt = p.get("mimeType", "")
        if p.get("filename"):
            continue
        body = p.get("body", {})
        data = body.get("data")
        if not data and body.get("attachmentId") and mt in ("text/html", "text/plain"):
            data = vykonaj(svc.users().messages().attachments().get(
                userId="me", messageId=mid, id=body["attachmentId"]))["data"]
        if not data:
            continue
        if mt == "text/html" and html is None:
            html = b64(data).decode("utf-8", "replace")
        elif mt == "text/plain" and txt is None:
            txt = b64(data).decode("utf-8", "replace")
    if html:
        return html
    if txt:
        return "<pre style='white-space:pre-wrap'>" + txt.replace("<", "&lt;") + "</pre>"
    return None


def main():
    mesiac = mesiac_z_argumentu()
    scan = BASE / "vystup" / f"scan_{mesiac}.csv"
    if not scan.exists():
        sys.exit(f"Chýba {scan} – najprv spusti: python 1_gmail_scan.py {mesiac}")

    with open(scan, encoding="utf-8-sig") as f:
        stare = {"✅ faktúra": "[+] faktúra", "❓ možno": "[?] možno", "🏦 výpis": "[#] výpis"}
        riadky = []
        for r in csv.DictReader(f, delimiter=";"):
            r["skupina"] = stare.get(r["skupina"], r["skupina"])
            if r["skupina"] in ("[+] faktúra", "[?] možno", "[#] výpis"):
                riadky.append(r)

    ciel = BASE / "vystup" / mesiac
    (ciel / "faktury").mkdir(parents=True, exist_ok=True)
    (ciel / "vypisy").mkdir(parents=True, exist_ok=True)

    hashe = {hashlib.sha256(p.read_bytes()).hexdigest()
             for d in ("faktury", "vypisy") for p in (ciel / d).iterdir() if p.is_file()}
    hesla = nacitaj_hesla()
    svc = get_service()
    zaznamy = []

    def uloz(r, meno, data, typ, poznamka=""):
        h = hashlib.sha256(data).hexdigest()
        priecinok = ciel / ("vypisy" if r["skupina"] == "[#] výpis" else "faktury")
        subor = priecinok / bezpecne_meno(f"{r['datum']}_{r['domena']}_{meno}")
        if h in hashe:
            poznamka = (poznamka + "; " if poznamka else "") + "duplicita – neuložené"
            subor_meno = ""
        else:
            i = 2
            while subor.exists():
                subor = subor.with_name(f"{subor.stem}_{i}{subor.suffix}")
                i += 1
            subor.write_bytes(data)
            hashe.add(h)
            subor_meno = subor.name
        zaznamy.append({
            "skupina": r["skupina"], "datum": r["datum"], "domena": r["domena"],
            "predmet": r["predmet"], "subor": subor_meno, "typ": typ,
            "poznamka": poznamka, "sha256": h[:16], "gmail_id": r["gmail_id"],
        })
        stav = "= duplicita" if not subor_meno else "OK"
        print(f"  {stav} {r['domena'][:22]:22} {meno[:60]}  {poznamka}")

    print(f"\nSťahujem {len(riadky)} mailov za {mesiac}…\n")
    for r in riadky:
        msg = vykonaj(svc.users().messages().get(userId="me", id=r["gmail_id"], format="full"))
        nasiel = False
        for p in casti(msg["payload"]):
            meno = p.get("filename") or ""
            att = p.get("body", {}).get("attachmentId")
            if not meno or not att:
                continue
            mt = p.get("mimeType", "")
            if not pripona(meno) and mt == "application/pdf":
                meno += ".pdf"
            ext = pripona(meno)
            if ext not in UZITOCNE | {"zip"}:
                continue
            if BALAST_PRILOHA.search(meno) and not (meno.lower().startswith("noname") and ext == "pdf"):
                continue
            if ext != "zip" and not povoleny(r["domena"], meno):
                continue
            data = b64(vykonaj(svc.users().messages().attachments().get(
                userId="me", messageId=r["gmail_id"], id=att))["data"])
            time.sleep(0.2)
            if ext == "zip":
                obsah, pozn = rozbal_zip(data, hesla)
                obsah = [(m2, d2) for m2, d2 in obsah if povoleny(r["domena"], m2)]
                if obsah:
                    for m2, d2 in obsah:
                        uloz(r, m2, d2, pripona(m2), f"zo ZIP {meno}; {pozn}")
                else:
                    uloz(r, meno, data, "zip", pozn)
            else:
                uloz(r, meno, data, ext)
            nasiel = True

        if not nasiel and r["skupina"] != "[#] výpis":
            html = telo_mailu(svc, r["gmail_id"], msg["payload"])
            if html:
                hlavicka = (f"<div style='font:12px sans-serif;border-bottom:1px solid #999;margin-bottom:8px'>"
                            f"<b>{r['predmet']}</b><br>{r['odosielatel']} · {r['datum']}</div>")
                uloz(r, bezpecne_meno(r["predmet"], 60) + ".html",
                     (hlavicka + html).encode("utf-8"), "html", "faktúra v tele mailu")
        time.sleep(0.2)

    manifest = ciel / "stiahnute.csv"
    with open(manifest, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(zaznamy[0].keys()) if zaznamy else ["subor"], delimiter=";")
        w.writeheader()
        w.writerows(zaznamy)

    ulozene = [z for z in zaznamy if z["subor"]]
    problem = [z for z in zaznamy if "heslo neznáme" in z["poznamka"] or "chyba" in z["poznamka"]]
    print(f"\nUložených súborov: {len(ulozene)} "
          f"(PDF {sum(z['typ']=='pdf' for z in ulozene)}, HTML {sum(z['typ']=='html' for z in ulozene)}, "
          f"XML/ISDOC {sum(z['typ'] in ('xml','isdoc') for z in ulozene)}, ZIP {sum(z['typ']=='zip' for z in ulozene)})")
    if problem:
        print("! Na kontrolu:")
        for z in problem:
            print(f"   {z['domena']}: {z['poznamka']}")
    print(f"Súpis: {manifest}\nPriečinok: {ciel}")


if __name__ == "__main__":
    main()
