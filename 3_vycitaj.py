"""
Krok 3 – vyčítanie údajov z faktúr (Claude API), zaradenie do obdobia, vyradenie duplicít.

Použitie:
    python 3_vycitaj.py            # predchádzajúci mesiac
    python 3_vycitaj.py 2026-09

Vstup:  vystup/RRRR-MM/faktury/ (z kroku 2) + voliteľne vstup/ (ručne stiahnuté PDF)
Výstup: vystup/RRRR-MM/faktury.csv  – jeden riadok na súbor, s údajmi a rozhodnutím
        výber a tlač potom: python tlac.py
Výsledky z API sa ukladajú do cache – opakované spustenie neplatí znova.
"""
import base64
import csv
import hashlib
import html as htmllib
import io
import json
import os
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import anthropic

import config

BASE = Path(__file__).resolve().parent

NASTROJ = {
    "name": "uloz_doklad",
    "description": "Uloží štruktúrované údaje vyčítané z dokladu.",
    "input_schema": {
        "type": "object",
        "properties": {
            "typ_dokladu": {"type": "string", "enum": [
                "faktúra", "dobropis", "zálohová/proforma", "pokladničný doklad/účtenka",
                "potvrdenie platby", "objednávka/potvrdenie objednávky", "výzva/upomienka", "iné"]},
            "dodavatel_nazov": {"type": ["string", "null"]},
            "dodavatel_ico": {"type": ["string", "null"], "description": "IČO bez medzier; zahraničné reg. číslo ak IČO nie je"},
            "dodavatel_ic_dph": {"type": ["string", "null"]},
            "odberatel_nazov": {"type": ["string", "null"]},
            "odberatel_ico": {"type": ["string", "null"]},
            "cislo_dokladu": {"type": ["string", "null"]},
            "variabilny_symbol": {"type": ["string", "null"]},
            "datum_vystavenia": {"type": ["string", "null"], "description": "RRRR-MM-DD"},
            "dzp": {"type": ["string", "null"], "description": "dátum zdaniteľného plnenia / dodania, RRRR-MM-DD; null ak nie je uvedený"},
            "datum_splatnosti": {"type": ["string", "null"], "description": "RRRR-MM-DD"},
            "obdobie_od": {"type": ["string", "null"], "description": "zúčtovacie obdobie od, RRRR-MM-DD"},
            "obdobie_do": {"type": ["string", "null"], "description": "zúčtovacie obdobie do, RRRR-MM-DD"},
            "suma_spolu": {"type": ["number", "null"], "description": "celková suma na úhradu vrátane DPH"},
            "mena": {"type": ["string", "null"]},
            "suma_dph": {"type": ["number", "null"]},
            "iban_dodavatela": {"type": ["string", "null"]},
            "sposob_uhrady": {"type": ["string", "null"], "description": "prevod, karta, inkaso, hotovosť, …"},
            "uz_uhradene": {"type": ["boolean", "null"], "description": "doklad uvádza, že je už zaplatený"},
            "predmet": {"type": ["string", "null"], "description": "krátko čo sa fakturuje (max 60 znakov)"},
            "istota": {"type": "number", "description": "0–1, ako spoľahlivo sa údaje podarilo vyčítať"},
            "poznamka": {"type": ["string", "null"]},
        },
        "required": ["typ_dokladu", "istota"],
    },
}

PROMPT = """Si účtovný asistent. Z priloženého dokladu vyčítaj údaje a VŽDY odpovedz zavolaním nástroja uloz_doklad (bez ďalšieho textu).
Pravidlá:
- Dátumy vždy RRRR-MM-DD. Ak údaj v doklade nie je, daj null – nič nedomýšľaj.
- DZP = "dátum zdaniteľného plnenia", "dátum dodania", "Lieferdatum", "date of supply", "tax point".
  Ak nie je uvedený, daj null (nepoužívaj dátum vystavenia).
- suma_spolu = konečná suma dokladu vrátane DPH (pri dobropise záporná).
- Ak to nie je daňový doklad (napr. len potvrdenie objednávky, obchodné podmienky, upomienka), zvoľ zodpovedajúci typ.
Kontext z e-mailu: {kontext}"""


def mesiac_z_argumentu():
    if len(sys.argv) > 1:
        return sys.argv[1]
    prvy = date.today().replace(day=1)
    return f"{(prvy - timedelta(days=1)):%Y-%m}"


def api_kluc():
    k = os.environ.get("ANTHROPIC_API_KEY")
    subor = BASE / "secrets" / "anthropic_key.txt"
    if not k and subor.exists():
        k = subor.read_text().strip()
    if not k:
        sys.exit("Chýba API kľúč: secrets/anthropic_key.txt")
    return k


def skrat_pdf(data: bytes, max_stran: int) -> bytes:
    try:
        from pypdf import PdfReader, PdfWriter
        r = PdfReader(io.BytesIO(data))
        if len(r.pages) <= max_stran:
            return data
        w = PdfWriter()
        for p in r.pages[:max_stran]:
            w.add_page(p)
        out = io.BytesIO()
        w.write(out)
        return out.getvalue()
    except Exception:
        return data


def html_na_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h\d)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmllib.unescape(s)
    return re.sub(r"[ \t ]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()[:20000]


def vycitaj(klient, subor: Path, kontext: str) -> dict:
    ext = subor.suffix.lower()
    if ext == ".pdf":
        data = skrat_pdf(subor.read_bytes(), config.MAX_STRAN_NA_EXTRAKCIU)
        obsah = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                  "data": base64.b64encode(data).decode()}}]
    elif ext == ".html":
        obsah = [{"type": "text", "text": "DOKLAD (text e-mailu):\n" + html_na_text(subor.read_text("utf-8", "replace"))}]
    else:  # xml / isdoc
        obsah = [{"type": "text", "text": "DOKLAD (XML):\n" + subor.read_text("utf-8", "replace")[:30000]}]
    obsah.append({"type": "text", "text": PROMPT.format(kontext=kontext)})
    odp = klient.messages.create(
        model=config.MODEL_EXTRAKCIA, max_tokens=1500,
        tools=[NASTROJ], tool_choice={"type": "auto"},
        messages=[{"role": "user", "content": obsah}],
    )
    for blok in odp.content:
        if blok.type == "tool_use":
            return dict(blok.input)
    # záloha: model odpovedal textom – skúsime z neho vytiahnuť JSON
    text = "".join(getattr(b, "text", "") for b in odp.content)
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {"typ_dokladu": "iné", "istota": 0, "poznamka": "model nevrátil údaje: " + text[:150]}


def d(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def zarad(u: dict, mesiac: str):
    """Vráti (rozhodnutie, dôvod). rozhodnutie: TLAČ / ? TLAČ / MIMO / NIE DOKLAD"""
    r, m = map(int, mesiac.split("-"))
    od = date(r, m, 1)
    do = (od.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    typ = u.get("typ_dokladu", "iné")
    if typ in ("objednávka/potvrdenie objednávky", "výzva/upomienka", "iné"):
        return "NIE DOKLAD", f"typ: {typ}"

    dzp, vyst = d(u.get("dzp")), d(u.get("datum_vystavenia"))
    o_od, o_do = d(u.get("obdobie_od")), d(u.get("obdobie_do"))
    zasahuje = bool(o_od and o_do and o_od <= do and o_do >= od)

    # účtenky / potvrdenia platby: dátum = dátum služby -> striktne
    if typ in ("pokladničný doklad/účtenka", "potvrdenie platby"):
        ref = dzp or vyst or o_od
        if ref and od <= ref <= do:
            return "TLAČ", f"{typ} z {ref}"
        if ref:
            return "MIMO", f"{typ} z {ref}"
        return "? TLAČ", f"{typ} bez dátumu – over"
    # obdobie plnenia celé po mesiaci (predplatné, pobyt…) -> mimo
    if o_od and o_od > do and not (dzp and od <= dzp <= do):
        return "MIMO", f"obdobie {o_od}–{o_do} je po {mesiac}"
    if typ == "zálohová/proforma":
        return "? TLAČ", "zálohová/proforma – nie je daňový doklad, over"
    if dzp:
        if od <= dzp <= do:
            return "TLAČ", f"DZP {dzp}"
        if dzp > do and (dzp - do).days <= config.HRANICA_DNI and zasahuje:
            return "? TLAČ", f"DZP {dzp}, ale obdobie {o_od}–{o_do} zasahuje do {mesiac}"
        return "MIMO", f"DZP {dzp} mimo {mesiac}"
    # DZP chýba
    ref = vyst
    if zasahuje:
        return "? TLAČ", f"bez DZP, obdobie {o_od}–{o_do} zasahuje do {mesiac}"
    if ref and od <= ref <= do + timedelta(days=config.HRANICA_DNI):
        return "? TLAČ", f"bez DZP, vystavená {ref}"
    if ref:
        return "MIMO", f"bez DZP, vystavená {ref}"
    return "? TLAČ", "chýba DZP aj dátum vystavenia – over"


def norm(s):
    return re.sub(r"[^0-9a-z]", "", (s or "").lower())


def kluc_duplicity(u: dict):
    dod = norm(u.get("dodavatel_ico")) or norm(u.get("dodavatel_nazov"))[:12]
    cis = norm(u.get("cislo_dokladu"))
    if dod and cis:
        return f"{dod}|{cis}"
    if dod and u.get("suma_spolu") is not None:
        return f"{dod}|{u.get('suma_spolu')}|{u.get('datum_vystavenia')}"
    return None


def kluc_suma(u: dict):
    """Druhý kľúč: prvé slovo dodávateľa + suma + dátum (receipt vs invoice bez čísla)."""
    nazov = norm((u.get("dodavatel_nazov") or "").replace("Sinch ", "").split(" ")[0])
    if nazov and u.get("suma_spolu") not in (None, 0) and u.get("datum_vystavenia"):
        return f"{nazov}|{u.get('suma_spolu')}|{u.get('datum_vystavenia')}"
    return None


def priorita(subor: Path):
    ext = subor.suffix.lower()
    if ext == ".pdf":
        return 0 if re.search(r"fakt|invoice|rechnung|_ni\.", subor.name, re.I) else 1
    return {".html": 3}.get(ext, 9)  # xml/isdoc sa netlačí


def main():
    mesiac = mesiac_z_argumentu()
    koren = BASE / "vystup" / mesiac
    zdroj = koren / "faktury"
    if not zdroj.exists():
        sys.exit(f"Chýba {zdroj} – najprv spusti krok 2.")

    meta = {}
    manifest = koren / "stiahnute.csv"
    if manifest.exists():
        with open(manifest, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f, delimiter=";"):
                if r.get("subor"):
                    meta[r["subor"]] = r

    subory = [p for p in sorted(zdroj.iterdir()) if p.is_file() and p.suffix.lower() in (".pdf", ".html", ".xml", ".isdoc")]
    rucne = BASE / "vstup"
    if rucne.exists():
        subory += [p for p in sorted(rucne.iterdir()) if p.suffix.lower() == ".pdf"]
    # pravidlá z config.LEN_SUBORY (napr. OMV len *_NI.pdf) platia aj pre už stiahnuté súbory
    def povoleny(p):
        casti = p.name.split("_", 2)
        dom = casti[1].lower() if len(casti) >= 3 else ""
        if any(i in dom for i in getattr(config, "IGNOROVANI_ODOSIELATELIA", [])):
            return False
        for d_, vzor in getattr(config, "LEN_SUBORY", {}).items():
            if d_ in dom:
                return re.search(vzor, p.name, re.I) is not None
        return True
    vynechane = [p.name for p in subory if not povoleny(p)]
    subory = [p for p in subory if povoleny(p)]
    if vynechane:
        print("Vynechané podľa pravidiel dodávateľa: " + ", ".join(vynechane))
    # XML, ku ktorému existuje PDF s rovnakým menom, nevyčítavame zvlášť
    pdf_stemy = {p.stem.lower() for p in subory if p.suffix.lower() == ".pdf"}
    subory = [p for p in subory if not (p.suffix.lower() in (".xml", ".isdoc") and p.stem.lower() in pdf_stemy)]

    cache_subor = koren / "vycitane_cache.json"
    cache = json.loads(cache_subor.read_text()) if cache_subor.exists() else {}
    klient = anthropic.Anthropic(api_key=api_kluc())

    vysledky = []
    print(f"\nVyčítavam {len(subory)} dokladov ({config.MODEL_EXTRAKCIA})…\n")
    for i, p in enumerate(subory, 1):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        m = meta.get(p.name, {})
        kontext = f"odosielateľ {m.get('domena', '?')}, predmet „{m.get('predmet', '')}“, prijatý {m.get('datum', '?')}"
        if h in cache:
            u = cache[h]
        else:
            try:
                u = vycitaj(klient, p, kontext)
            except anthropic.APIError as e:
                print(f"  X {p.name}: {e}")
                continue
            cache[h] = u
            cache_subor.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        rozh, dovod = zarad(u, mesiac)
        smer = "vydaná" if norm(u.get("dodavatel_ico")) == norm(config.MOJE_ICO) else "prijatá"
        vysledky.append({"subor": p, "u": u, "rozh": rozh, "dovod": dovod, "smer": smer, "meta": m})
        print(f"  [{i:2}/{len(subory)}] {rozh:10} {smer:7} {(u.get('dodavatel_nazov') or '?')[:24]:24} "
              f"{u.get('cislo_dokladu') or '':>16} {u.get('suma_spolu') or '':>9} {u.get('mena') or ''}  {dovod}")

    # Duplicity: v rámci rovnakého kľúča ponecháme dokument s najlepšou prioritou
    skupiny = {}
    for v in vysledky:
        k = kluc_duplicity(v["u"])
        if k:
            skupiny.setdefault(k, []).append(v)
    typ_poradie = {"faktúra": 0, "dobropis": 0, "pokladničný doklad/účtenka": 1, "zálohová/proforma": 2,
                   "potvrdenie platby": 3}
    def poradie_dokladu(v):
        return (typ_poradie.get(v["u"].get("typ_dokladu"), 5), priorita(v["subor"]))
    for k, zoz in skupiny.items():
        zoz.sort(key=poradie_dokladu)
        for v in zoz[1:]:
            v["duplicita_k"] = zoz[0]["subor"].name
    skupiny2 = {}
    for v in vysledky:
        k = kluc_suma(v["u"])
        if k and "duplicita_k" not in v:
            skupiny2.setdefault(k, []).append(v)
    for zoz in skupiny2.values():
        if len({kluc_duplicity(v["u"]) for v in zoz if kluc_duplicity(v["u"]) and norm(v["u"].get("cislo_dokladu"))}) > 1:
            continue  # rôzne čísla dokladov = rôzne doklady
        zoz.sort(key=poradie_dokladu)
        for v in zoz[1:]:
            v["duplicita_k"] = zoz[0]["subor"].name
    for v in vysledky:  # XML sa nikdy netlačí
        if v["subor"].suffix.lower() in (".xml", ".isdoc") and "duplicita_k" not in v:
            v["netlacit"] = "XML sa netlačí"

    # CSV
    stlpce = ["rozhodnutie", "dovod", "smer", "typ_dokladu", "dodavatel_nazov", "dodavatel_ico", "cislo_dokladu",
              "variabilny_symbol", "datum_vystavenia", "dzp", "obdobie_od", "obdobie_do", "datum_splatnosti",
              "suma_spolu", "mena", "suma_dph", "iban_dodavatela", "sposob_uhrady", "uz_uhradene", "predmet",
              "istota", "poznamka", "duplicita", "subor", "odosielatel_mailu", "predmet_mailu"]
    out = koren / "faktury.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=stlpce, delimiter=";", extrasaction="ignore")
        w.writeheader()
        poradie = {"TLAČ": 0, "? TLAČ": 1, "MIMO": 2, "NIE DOKLAD": 3}
        for v in sorted(vysledky, key=lambda v: (poradie.get(v["rozh"], 9), "duplicita_k" in v, v["u"].get("dzp") or "")):
            riadok = dict(v["u"])
            riadok.update({
                "rozhodnutie": v["rozh"], "dovod": v["dovod"], "smer": v["smer"],
                "duplicita": f"duplicita – tlačí sa {v['duplicita_k']}" if "duplicita_k" in v else (v.get("netlacit") or ""),
                "subor": v["subor"].name, "odosielatel_mailu": v["meta"].get("domena", ""),
                "predmet_mailu": v["meta"].get("predmet", ""),
            })
            if isinstance(riadok.get("suma_spolu"), float):
                riadok["suma_spolu"] = f"{riadok['suma_spolu']:.2f}".replace(".", ",")
            w.writerow(riadok)

    pocet = lambda r: sum(1 for v in vysledky if v["rozh"] == r and "duplicita_k" not in v)
    print(f"\nTLAČ: {pocet('TLAČ')} | ? TLAČ (na overenie): {pocet('? TLAČ')} | "
          f"MIMO obdobia: {pocet('MIMO')} | nie doklad: {pocet('NIE DOKLAD')} | "
          f"duplicít: {sum(1 for v in vysledky if 'duplicita_k' in v)}")
    print("\nĎalej: python tlac.py  – výber (+9 / -10) a tlač")
    print(f"Vydané: {sum(1 for v in vysledky if v['smer'] == 'vydaná')}")
    print(f"Tabuľka: {out}")


if __name__ == "__main__":
    main()
