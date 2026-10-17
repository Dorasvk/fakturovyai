"""
Krok 4 – výpis z účtu: platby, ku ktorým nemáme doklad (čo treba dorobiť ručne).

Použitie:
    python 4_nedostatky.py              # predchádzajúci mesiac – spracuje a uloží
    python 4_nedostatky.py 2026-09
    python 4_nedostatky.py --zobraz     # len zobrazí uložený zoznam (biela obrazovka)

Výpis: vystup/RRRR-MM/vypisy/*.pdf (SLSP). Doklady: všetky vystup/*/faktury.csv (aj naskenované bločky zo vstup/).
Platby z config.IGNOROVAT_PLATBY sa preskočia. Výstup: vystup/RRRR-MM/nedostatky.csv
"""
import csv
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import config
import tema

BASE = Path(__file__).resolve().parent
ZACIATOK = re.compile(r"^(\d{2}\.\d{2}\.\d{4}) (\d{2}\.\d{2}\.\d{4}) (.*)$")
SUMA = re.compile(r"(-\s?)?(\d{1,3}(?: \d{3})*,\d{2})\s*$")


def mesiac_z_argumentov():
    for a in sys.argv[1:]:
        if re.fullmatch(r"\d{4}-\d{2}", a):
            return a
    prvy = date.today().replace(day=1)
    return f"{(prvy - timedelta(days=1)):%Y-%m}"


def num(s):
    return float(s.replace(" ", "").replace(",", "."))


def cisla(s):
    return re.sub(r"\D", "", s or "").lstrip("0")


def nacitaj_vypis(pdf: Path):
    from pypdf import PdfReader
    text = "\n".join(p.extract_text() or "" for p in PdfReader(str(pdf)).pages)
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    m = re.search(r"Účtovné obdobie\s+(\d{2})\. (\d{2})\. (\d{4})", text)
    obdobie = f"{m.group(3)}-{m.group(2)}" if m else ""
    tx, akt = [], None
    for riadok in text.splitlines():
        riadok = riadok.strip()
        z = ZACIATOK.match(riadok)
        if z:
            akt = {"datum": datetime.strptime(z.group(1), "%d.%m.%Y").date(), "typ": z.group(3), "riadky": []}
            s = SUMA.search(z.group(3))
            if s and not re.search(r"\d{2}\.\d{2}\.\d{4}", z.group(3)[s.start() - 3:]):
                akt["typ"] = z.group(3)[:s.start()].strip()
                akt["suma"] = -num(s.group(2)) if s.group(1) else num(s.group(2))
                tx.append(akt); akt = None
            continue
        if akt is None:
            continue
        if re.fullmatch(r"-?\s?\d{1,3}(?: \d{3})*,\d{2}", riadok):
            akt["suma"] = -num(riadok.lstrip("- ")) if riadok.startswith("-") else num(riadok)
            tx.append(akt); akt = None
        else:
            akt["riadky"].append(riadok)
    for t in tx:
        popis = " ".join(t["riadky"])
        t["popis"] = popis
        vs = re.search(r"VS:\s*(\d+)", popis) or re.search(r"/VS(\d+)", popis)
        t["vs"] = vs.group(1) if vs else ""
        m = (re.search(r"Názov protiúčtu:\s*(.+?)(?: VS:| SS:| KS:|$)", popis)
             or re.search(r"Inkasant: \S+?~(.+?)(?: Referencia|$)", popis))
        if m:
            t["protistrana"] = m.group(1).strip()
        elif t["typ"].lower().startswith(("platba kartou", "výber kartou")):
            obch = [r for r in t["riadky"] if not r.startswith("Č. k.")]
            t["protistrana"] = re.sub(r"\s\d{2}\. \d{2}\. ?\d{0,4}.*$", "", obch[0]) if obch else ""
        else:
            t["protistrana"] = ""
        cudzia = next((re.fullmatch(r"(\d{1,3}(?: \d{3})*,\d{2})\s?([A-Z]{3})", r) for r in t["riadky"]
                       if re.fullmatch(r"\d{1,3}(?: \d{3})*,\d{2}\s?[A-Z]{3}", r)), None)
        t["cudzia_mena"] = f"{cudzia.group(1)} {cudzia.group(2)}" if cudzia else ""
    return obdobie, tx


def nacitaj_doklady():
    doklady = []
    for f in sorted((BASE / "vystup").glob("*/faktury.csv")):
        with open(f, encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh, delimiter=";"):
                try:
                    r["_suma"] = num(r["suma_spolu"]) if r.get("suma_spolu") else None
                except ValueError:
                    r["_suma"] = None
                d = r.get("dzp") or r.get("datum_vystavenia") or ""
                try:
                    r["_datum"] = date.fromisoformat(d)
                except ValueError:
                    r["_datum"] = None
                r["_meno"] = " ".join([r.get("dodavatel_nazov") or "", r.get("odosielatel_mailu") or "",
                                        r.get("subor") or ""]).lower()
                doklady.append(r)
    return doklady


GENERICKE = {"slovakia", "slovensko", "s.r.o", "sro", "gmbh", "limited", "payment", "payments", "online",
             "dublin", "bratislava", "praha", "wien", "credit", "subscr", "platba", "s.r", "spol", "a.s",
             "eur", "czk", "sepa", "kartou", "faktura", "invoice", "pdf", "html", "com", "www"}


def slova(s):
    return {w for w in re.findall(r"[a-z0-9]{3,}", (s or "").lower()) if w not in GENERICKE and not w.isdigit()}


def najdi_doklad(t, doklady):
    vs = cisla(t["vs"])
    meno = slova(t["protistrana"] + " " + t["popis"][:120])
    for d in doklady:
        if vs and len(vs) >= 4 and vs in (cisla(d.get("variabilny_symbol")), cisla(d.get("cislo_dokladu"))):
            return d, "VS"
    for d in doklady:
        if d["_suma"] is None or abs(abs(d["_suma"]) - abs(t["suma"])) > 0.01:
            continue
        menoz = bool(meno & slova(d["_meno"]))
        if d["_datum"]:
            rozdiel = (t["datum"] - d["_datum"]).days       # platba - doklad
            if not (-7 <= rozdiel <= 45):
                continue
        if menoz:
            return d, "suma + názov"
    return None, ""


def napoveda(t):
    text = (t["protistrana"] + " " + t["popis"]).lower()
    for vzor, rada in getattr(config, "NAPOVEDA", {}).items():
        if re.search(vzor, text):
            return rada
    return "dohľadaj doklad (faktúra / bloček) a ulož ho do vstup/"


def spracuj(mesiac):
    koren = BASE / "vystup" / mesiac
    vypisy = sorted((koren / "vypisy").glob("*.pdf")) if (koren / "vypisy").exists() else []
    if not vypisy:
        print("! Výpis za tento mesiac chýba (vystup/%s/vypisy/*.pdf) – nedostatky sa nedajú zistiť." % mesiac)
        return None
    doklady = nacitaj_doklady()
    ignor = [re.compile(v, re.I) for v in getattr(config, "IGNOROVAT_PLATBY", [])]
    riadky, ignorovane, sparovane = [], 0, 0
    for pdf in vypisy:
        obdobie, tx = nacitaj_vypis(pdf)
        if obdobie and obdobie != mesiac:
            continue
        print(f"Výpis {pdf.name}: {len(tx)} pohybov")
        for t in tx:
            text = f"{t['typ']} {t['protistrana']} {t['popis']}"
            if any(v.search(text) for v in ignor):
                ignorovane += 1
                continue
            d, ako = najdi_doklad(t, doklady)
            if d:
                sparovane += 1
                continue
            riadky.append({"datum": t["datum"].isoformat(), "suma": f"{t['suma']:.2f}".replace(".", ","),
                           "cudzia_mena": t["cudzia_mena"], "protistrana": t["protistrana"],
                           "typ": t["typ"], "vs": t["vs"], "co_urobit": napoveda(t)})
    out = koren / "nedostatky.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["datum", "suma", "cudzia_mena", "protistrana", "typ", "vs", "co_urobit"],
                           delimiter=";")
        w.writeheader(); w.writerows(riadky)
    print(f"S dokladom: {sparovane} | ignorované (výbery, poplatky, odvody…): {ignorovane} | BEZ DOKLADU: {len(riadky)}")
    return out


def zobraz(mesiac):
    out = BASE / "vystup" / mesiac / "nedostatky.csv"
    tema.obrazovka(tema.BIELA)
    if not out.exists():
        print("\n Nedostatky: výpis za %s zatiaľ nie je spracovaný.\n" % mesiac)
        return
    with open(out, encoding="utf-8-sig") as f:
        riadky = list(csv.DictReader(f, delimiter=";"))
    print(f"\n{tema.TUCNE} PLATBY BEZ DOKLADU · {mesiac} · {len(riadky)} položiek{tema.RESET}{tema.BIELA}")
    print(" Toto treba dorobiť ručne – doklad ulož do ~/faktury-agent/vstup/ a spusti znova.\n")
    print(f" {'#':>3}  {'dátum':10}  {'suma':>10}  {'protistrana':32}  čo urobiť")
    print(" " + "─" * 110)
    spolu = 0.0
    for i, r in enumerate(riadky, 1):
        suma = r["suma"] + (f" ({r['cudzia_mena']})" if r["cudzia_mena"] else "")
        spolu += num(r["suma"])
        print(f" {i:>3}  {r['datum']:10}  {r['suma']:>10}  {(r['protistrana'] or r['typ'])[:32]:32}  {r['co_urobit']}")
        if r["cudzia_mena"]:
            print(f" {'':>3}  {'':10}  {'':>10}  {'(' + r['cudzia_mena'] + ')':32}")
    print(" " + "─" * 110)
    print(f" Spolu bez dokladu: {spolu:.2f} EUR".replace(".", ","))


def main():
    mesiac = mesiac_z_argumentov()
    if "--zobraz" in sys.argv:
        zobraz(mesiac)
        try:
            input(f"\n{tema.TUCNE} Enter = koniec{tema.RESET}{tema.BIELA}")
        except (EOFError, KeyboardInterrupt):
            pass
        tema.koniec()
    else:
        spracuj(mesiac)


if __name__ == "__main__":
    main()
