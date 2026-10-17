"""Skórovanie: je mail faktúra? Výsledok: (skore, skupina, dovody)."""
import re

import config

SILNE_PREDMET = re.compile(
    r"fakt[uú]r|invoice|rechnung|vy[uú][cč]tovan|da[nň]ov[yý] doklad|dobropis|"
    r"\breceipt\b|\bdoklad\b|doklad k|\bFA\b|e-?fakt[uú]r|potvrdenie platby|platobn[eé] potvrdenie",
    re.I,
)
SILNE_PRILOHA = re.compile(
    r"fakt[uú]r|invoice|rechnung|doklad|receipt|potvrdenie_platby|^fa[-_ ]?\d|_invoice|^\d{8,}\.pdf$",
    re.I,
)
# prílohy, ktoré samé osebe NIE sú faktúra
BALAST_PRILOHA = re.compile(
    r"podmienk|vop|gtc|odst[uú]pen|odstupeni|zmluv|ticket|boarding|vstupenk|"
    r"\.png$|\.jpe?g$|\.gif$|^image\d|^noname$|logo|icon",
    re.I,
)
MARKETING = re.compile(
    r"zľav|zlav|akcia|webin|newsletter|novink|benefit|ohodno[tť]|ako bol|"
    r"prihl[aá]ste sa|vitajte|welcome|terms of service|regulamin|authentication code|"
    r"čoskoro|predtým ako|special request|message from|you have a message|"
    r"nový vzhľad|nov[yý] dizajn|otestujte|uvid[ií]me sa|v praxi|reminder|zmeny v",
    re.I,
)


def ohodnot(odosielatel, predmet, snippet, prilohy, labels):
    if any(i in odosielatel.lower() for i in getattr(config, "IGNOROVANI_ODOSIELATELIA", [])):
        return -99, "[-] šum", "ignorovaný odosielateľ"
    s, d = 0, []
    predmet = predmet or ""
    fin = [p for p in prilohy if p.rsplit(".", 1)[-1].lower() in config.PRILOHY]
    zmysl = [p for p in fin if not BALAST_PRILOHA.search(p)]

    if SILNE_PREDMET.search(predmet):
        s += 3; d.append("faktúra v predmete")
    if any(SILNE_PRILOHA.search(p) for p in zmysl):
        s += 3; d.append("faktúrová príloha")
    elif zmysl:
        s += 1; d.append("príloha " + ", ".join(zmysl[:2])[:40])
    adresa = odosielatel.lower().split("<")[-1]
    if re.search(r"(fakt[uú]r|invoic|billing|receipt|payments?)[^@]*@", adresa):
        s += 2; d.append("fakturačná adresa odosielateľa")
    if any(o in odosielatel.lower() for o in config.ZNAMI_ODOSIELATELIA):
        s += 1; d.append("známy dodávateľ")
    if SILNE_PREDMET.search(snippet or "") and not SILNE_PREDMET.search(predmet):
        s += 1; d.append("faktúra v texte")
    if MARKETING.search(predmet):
        s -= 3; d.append("marketing/notifikácia")
    if re.search(r"@(news|newsletter|marketing)\.", odosielatel.lower()):
        s -= 3; d.append("newsletter odosielateľ")
    if labels & {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"}:
        s -= 3; d.append("kategória reklama")
    if "SENT" in labels:
        s -= 1; d.append("odoslaný mnou")
    if re.match(r"\s*(re|fw|fwd|aw)\s*:", predmet, re.I) and not SILNE_PREDMET.search(predmet):
        s -= 1; d.append("konverzácia")
    if fin and not zmysl and s < 4:
        d.append("len podmienky/obrázky")

    if re.search(r"v[yý]pis .*[uú][cč]et", predmet, re.I) and "slsp" in odosielatel.lower():
        return 10, "[#] výpis", "výpis z účtu SLSP"
    skupina = "[+] faktúra" if s >= 4 else ("[?] možno" if s >= 2 else "[-] šum")
    return s, skupina, "; ".join(d)
