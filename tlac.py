"""
Výber a tlač podkladov v Termináli.

Použitie:
    python tlac.py            # predchádzajúci mesiac, ovládanie šípkami
    python tlac.py 2026-09
    python tlac.py --text     # textový režim s príkazmi +9 / -10

Šípkový režim:
    ↑ ↓ (PgUp PgDn)  pohyb        MEDZERNÍK  označiť / odznačiť
    +9 / -10 / +3-7  napíš a potvrď Enterom
    ENTER alebo o    náhľad       t          tlačiť (s potvrdením)
    r                návrh z kroku 3 (zruší ručné zmeny)
    q                koniec (výber sa uloží)

Textový režim – príkazy:
    +9        pridať č. 9 do tlače        -10      vyradiť č. 10
    +3-7      pridať rozsah               +9 +12 -4  viac naraz
    o 9       otvoriť č. 9 v Náhľade
    z         zobraziť zoznam znova       t        tlačiť (s potvrdením)
    q         koniec (výber sa uloží)

Tlač: faktúry 1. strana (dodávatelia v config.TLAC_CELE celé), výpis celý, čiernobielo, jednostranne.
Výber sa ukladá do vystup/RRRR-MM/vyber.json.
"""
import csv
import curses
import json
import locale
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import config
import tema

BASE = Path(__file__).resolve().parent
CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def mesiac_z_argumentov(args):
    for a in args:
        if re.fullmatch(r"\d{4}-\d{2}", a):
            return a
    prvy = date.today().replace(day=1)
    return f"{(prvy - timedelta(days=1)):%Y-%m}"


def najdi_subor(meno, koren):
    for d in (koren / "faktury", BASE / "vstup"):
        p = d / meno
        if p.exists():
            return p
    return None


def html_na_pdf(html: Path):
    pdf = html.with_suffix(".pdf")
    if pdf.exists():
        return pdf
    if not CHROME.exists():
        print(f"  ! Chýba Google Chrome – HTML sa nedá previesť: {html.name}")
        return None
    subprocess.run([str(CHROME), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.resolve().as_uri()],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    return pdf if pdf.exists() else None


def otoc_na_vysku(pdf: Path, koren: Path) -> Path:
    """Ak má PDF strany na šírku, vytvorí kópiu otočenú na výšku (vystup/RRRR-MM/_tlac/)."""
    try:
        from pypdf import PdfReader, PdfWriter
        r = PdfReader(str(pdf))
        sirka = [p for p in r.pages if float(p.mediabox.width) > float(p.mediabox.height)
                 and (p.get("/Rotate") or 0) % 180 == 0]
        if not sirka:
            return pdf
        w = PdfWriter()
        for p in r.pages:
            if float(p.mediabox.width) > float(p.mediabox.height) and (p.get("/Rotate") or 0) % 180 == 0:
                p.rotate(90)
            w.add_page(p)
        ciel = koren / "_tlac"
        ciel.mkdir(exist_ok=True)
        out = ciel / pdf.name
        with open(out, "wb") as f:
            w.write(f)
        return out
    except Exception as e:
        print(f"  ! otočenie zlyhalo ({e}), tlačím originál")
        return pdf


def nacitaj_polozky(koren):
    polozky = []
    csv_subor = koren / "faktury.csv"
    if not csv_subor.exists():
        sys.exit(f"Chýba {csv_subor} – najprv spusti: python 3_vycitaj.py")
    with open(csv_subor, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            p = najdi_subor(r["subor"], koren)
            if not p:
                continue
            ext = p.suffix.lower()
            if ext in (".xml", ".isdoc"):
                continue  # XML sa netlačí ani nezobrazuje
            dup = r.get("duplicita", "")
            rozh = "duplicita" if dup.startswith("duplicita") else r["rozhodnutie"].replace("❓", "?")
            cele = any(d in r.get("odosielatel_mailu", "").lower() or d in p.name.lower() for d in config.TLAC_CELE)
            polozky.append({
                "subor": p, "rozh": rozh, "dzp": r.get("dzp") or r.get("datum_vystavenia") or "",
                "dodavatel": r.get("dodavatel_nazov") or r.get("odosielatel_mailu") or "?",
                "cislo": r.get("cislo_dokladu") or "", "suma": r.get("suma_spolu") or "",
                "mena": r.get("mena") or "", "dovod": r.get("dovod", ""), "dup": dup,
                "smer": r.get("smer", ""), "cele": cele,
                "default": rozh in ("TLAČ", "? TLAČ"),
            })
    for p in sorted((koren / "vypisy").glob("*.pdf")) if (koren / "vypisy").exists() else []:
        polozky.append({"subor": p, "rozh": "VÝPIS", "dzp": "", "dodavatel": "výpis z účtu",
                        "cislo": p.stem, "suma": "", "mena": "", "dovod": "", "dup": "",
                        "smer": "", "cele": True, "default": True})
    return polozky


def zobraz(polozky, vyber):
    print(f"\n {'#':>3}  tlač  {'rozhodnutie':11} {'DZP':10}  {'dodávateľ':24} {'číslo':16} {'suma':>11}")
    print(" " + "-" * 92)
    for i, p in enumerate(polozky, 1):
        x = "[x]" if vyber[p["subor"].name] else "[ ]"
        suma = f"{p['suma']} {p['mena']}".strip()
        info = p["dup"].replace("duplicita – tlačí sa ", "→ ") if p["dup"] else p["dovod"]
        if p["smer"] == "vydaná":
            info = "VYDANÁ · " + info
        if p["cele"] and p["rozh"] != "VÝPIS":
            info = "celá · " + info
        print(f" {i:>3}  {x}   {p['rozh'][:11]:11} {p['dzp'][:10]:10}  {p['dodavatel'][:24]:24} "
              f"{p['cislo'][:16]:16} {suma[:11]:>11}  {info[:45]}")
    n = sum(1 for p in polozky if vyber[p["subor"].name])
    print(f"\n Vybraných na tlač: {n}   (+9 / -10 / +3-7 / o 9 / r návrh / z / t / q)")


def cisla(token, n):
    m = re.fullmatch(r"(\d+)(?:-(\d+))?", token)
    if not m:
        return []
    a = int(m.group(1)); b = int(m.group(2) or a)
    return [i for i in range(min(a, b), max(a, b) + 1) if 1 <= i <= n]


def tlac(polozky, vyber):
    uloha = [p for p in polozky if vyber[p["subor"].name]]
    if not uloha:
        print("Nič nie je vybrané.")
        return
    print(f"\nTlačiareň: {config.TLACIAREN} · čiernobielo · jednostranne")
    for p in uloha:
        print(f"  {'celá' if p['cele'] else '1. str.':7} {p['subor'].name}")
    if input(f"\nVytlačiť {len(uloha)} dokumentov? (a/n): ").strip().lower() not in ("a", "ano", "áno", "y"):
        print("Zrušené.")
        return
    for p in uloha:
        subor = p["subor"]
        if subor.suffix.lower() == ".html":
            subor = html_na_pdf(subor)
            if not subor:
                continue
        subor = otoc_na_vysku(subor, p["subor"].parents[1] if p["subor"].parent.name in ("faktury", "vypisy") else BASE)
        volby = ["-o", "fit-to-page"] + ([] if p["cele"] else ["-o", "page-ranges=1"])
        r = subprocess.run(["lp", "-d", config.TLACIAREN, *config.TLAC_VOLBY, *volby, str(subor)],
                           capture_output=True, text=True)
        print(f"  {'OK' if r.returncode == 0 else 'X ' + r.stderr.strip()} {subor.name}")


# numerická klávesnica v "aplikačnom" režime posiela ESC O <znak>
NUMPAD = {"k": "+", "m": "-", "M": "\n", "n": ".", **{chr(ord("p") + i): str(i) for i in range(10)}}
NUMPAD_KODY = {curses.KEY_C1: "1", curses.KEY_C3: "3", curses.KEY_B2: "5",
               curses.KEY_A1: "7", curses.KEY_A3: "9", 580: "-", 579: "+"}


def citaj_klaves(scr):
    """Vráti (kód, znak). Rozumie slovenskej klávesnici aj numerickej klávesnici."""
    try:
        wk = scr.get_wch()
    except curses.error:
        return None, ""
    if isinstance(wk, int):
        z = NUMPAD_KODY.get(wk)
        if z:
            return ord(z), z
        return wk, ""
    if wk == "\x1b":                       # ESC – samostatný, alebo začiatok sekvencie numpadu
        scr.nodelay(True)
        try:
            dalsie = ""
            for _ in range(2):
                try:
                    dalsie += scr.get_wch()
                except curses.error:
                    break
        finally:
            scr.nodelay(False)
        if len(dalsie) == 2 and dalsie[0] == "O" and dalsie[1] in NUMPAD:
            z = NUMPAD[dalsie[1]]
            return ord(z), z
        return 27, ""
    return ord(wk) if len(wk) == 1 else -1, wk


def sipkovy_rezim(polozky, vyber, uloz):
    """Vráti 't' ak chce používateľ tlačiť, inak None."""
    locale.setlocale(locale.LC_ALL, "")
    ZELENY = getattr(config, "TEMA", "normal") == "zeleny"

    def kresli(scr, kurzor, hore):
        scr.erase()
        vys, sir = scr.getmaxyx()
        n = sum(1 for p in polozky if vyber[p["subor"].name])
        hlav = " ↑↓ · MEDZERA označiť · +9 -3-7 · ENTER náhľad · r návrh · t tlač · q koniec"
        z = curses.color_pair(10) if ZELENY else 0
        scr.addnstr(0, 0, f" Vybraných na tlač: {n}/{len(polozky)}  |" + hlav, sir - 1, curses.A_BOLD | z)
        scr.addnstr(1, 0, f"  {'#':>3} tlač {'rozhodnutie':11} {'DZP':10} {'dodávateľ':24} {'číslo':16} {'suma':>12}  info",
                    sir - 1, curses.A_UNDERLINE | z)
        riadkov = vys - 3
        for j, i in enumerate(range(hore, min(hore + riadkov, len(polozky)))):
            p = polozky[i]
            x = "[x]" if vyber[p["subor"].name] else "[ ]"
            rozh = p["rozh"]
            suma = f"{p['suma']} {p['mena']}".strip()
            info = p["dup"].replace("duplicita – tlačí sa ", "→ ") if p["dup"] else p["dovod"]
            if p["smer"] == "vydaná":
                info = "VYDANÁ · " + info
            if p["cele"] and p["rozh"] != "VÝPIS":
                info = "celá · " + info
            text = (f"  {i + 1:>3} {x}  {rozh[:11]:11} {p['dzp'][:10]:10} {p['dodavatel'][:24]:24} "
                    f"{p['cislo'][:16]:16} {suma[:12]:>12}  {info}")
            attr = curses.A_NORMAL
            if ZELENY:
                if vyber[p["subor"].name]:
                    attr = curses.color_pair(11) | curses.A_BOLD
                else:
                    attr = curses.color_pair(12)
            elif curses.has_colors():
                if vyber[p["subor"].name]:
                    attr = curses.color_pair(1)
                elif p["rozh"] in ("MIMO", "NIE DOKLAD", "duplicita"):
                    attr = curses.color_pair(3)
                if p["rozh"].startswith("?"):
                    attr |= curses.A_BOLD
            if i == kurzor:
                attr |= curses.A_REVERSE
            scr.addnstr(2 + j, 0, text, sir - 1, attr)
        p = polozky[kurzor]
        scr.addnstr(vys - 1, 0, f" {p['subor'].name}", sir - 1, curses.A_DIM | z)
        scr.refresh()

    def beh(scr):
        nonlocal ZELENY
        curses.curs_set(0)
        # numerickú klávesnicu prepneme do "číselného" režimu -> posiela + - 0-9 ako bežné znaky
        sys.stdout.write("\033>")
        sys.stdout.flush()
        if curses.has_colors():
            curses.start_color(); curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(3, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
            if ZELENY:
                v256 = curses.COLORS >= 256
                cierna = 16 if v256 else curses.COLOR_BLACK
                f = lambda k, d: getattr(config, k, d) if v256 else curses.COLOR_GREEN
                curses.init_pair(10, f("FARBA_TEXT", 40), cierna)        # text, hlavička
                curses.init_pair(11, f("FARBA_VYBRANE", 46), cierna)     # vybrané
                curses.init_pair(12, f("FARBA_NEVYBRANE", 28), cierna)   # nevybrané
                scr.bkgd(" ", curses.color_pair(10))
        else:
            ZELENY = False
        kurzor, hore = 0, 0
        prikaz = ""
        while True:
            vys = scr.getmaxyx()[0]
            riadkov = max(1, vys - 3)
            if kurzor < hore:
                hore = kurzor
            elif kurzor >= hore + riadkov:
                hore = kurzor - riadkov + 1
            kresli(scr, kurzor, hore)
            if prikaz:
                vys2, sir2 = scr.getmaxyx()
                z = curses.color_pair(11) | curses.A_BOLD if ZELENY else curses.A_BOLD
                scr.addnstr(vys2 - 1, 0, f" > {prikaz}_   (Enter potvrdiť · Esc zrušiť)".ljust(sir2 - 1), sir2 - 1, z)
                scr.refresh()
            k, _ = citaj_klaves(scr)
            if k is None:
                continue
            # rozpísaný príkaz +9 / -3-7 / +2 +5
            if prikaz or k in (ord("+"), ord("-")):
                if k in (10, 13, curses.KEY_ENTER):
                    for t in re.findall(r"[+-][\d-]+", prikaz):
                        for i in cisla(t[1:], len(polozky)):
                            vyber[polozky[i - 1]["subor"].name] = t[0] == "+"
                    uloz()
                    prikaz = ""
                elif k == 27:
                    prikaz = ""
                elif k in (curses.KEY_BACKSPACE, 127, 8):
                    prikaz = prikaz[:-1]
                elif 0 <= k < 0x110000 and chr(k) in "+-0123456789 ":
                    prikaz += chr(k)
                continue
            if k in (curses.KEY_UP, ord("k")):
                kurzor = max(0, kurzor - 1)
            elif k in (curses.KEY_DOWN, ord("j")):
                kurzor = min(len(polozky) - 1, kurzor + 1)
            elif k == curses.KEY_PPAGE:
                kurzor = max(0, kurzor - riadkov)
            elif k == curses.KEY_NPAGE:
                kurzor = min(len(polozky) - 1, kurzor + riadkov)
            elif k == ord(" "):
                meno = polozky[kurzor]["subor"].name
                vyber[meno] = not vyber[meno]
                uloz()
                kurzor = min(len(polozky) - 1, kurzor + 1)
            elif k in (10, 13, curses.KEY_ENTER, ord("o")):
                subprocess.Popen(["open", str(polozky[kurzor]["subor"])])
            elif k == ord("r"):
                for p in polozky:
                    vyber[p["subor"].name] = p["default"]
                uloz()
            elif k == ord("t"):
                return "t"
            elif k == ord("q"):
                return None

    return curses.wrapper(beh)


def main():
    mesiac = mesiac_z_argumentov(sys.argv[1:])
    koren = BASE / "vystup" / mesiac
    polozky = nacitaj_polozky(koren)
    if not polozky:
        sys.exit("Nič na zobrazenie.")
    vyber_subor = koren / "vyber.json"
    ulozene = {}
    csv_subor = koren / "faktury.csv"
    if vyber_subor.exists() and vyber_subor.stat().st_mtime > csv_subor.stat().st_mtime:
        ulozene = json.loads(vyber_subor.read_text())
    vyber = {p["subor"].name: ulozene.get(p["subor"].name, p["default"]) for p in polozky}

    def uloz():
        vyber_subor.write_text(json.dumps(vyber, ensure_ascii=False, indent=1))

    if "--text" not in sys.argv:
        while True:
            akcia = sipkovy_rezim(polozky, vyber, uloz)
            uloz()
            tema.obrazovka(tema.ZELENA)
            if akcia == "t":
                tlac(polozky, vyber)
                if input("\nSpäť do výberu? (a/n): ").strip().lower() in ("a", "ano", "áno", "y"):
                    continue
            print("Výber uložený.")
            tema.koniec()
            return

    tema.obrazovka(tema.ZELENA)
    print(f"\nPodklady za {mesiac}")
    zobraz(polozky, vyber)
    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            cmd = "q"
        if not cmd:
            continue
        if cmd == "q":
            uloz(); print("Výber uložený."); tema.koniec(); return
        if cmd == "z":
            zobraz(polozky, vyber); continue
        if cmd == "r":
            for p in polozky:
                vyber[p["subor"].name] = p["default"]
            uloz(); zobraz(polozky, vyber); continue
        if cmd == "t":
            uloz(); tlac(polozky, vyber); continue
        if cmd.startswith("o"):
            for t in cmd[1:].split():
                for i in cisla(t, len(polozky)):
                    subprocess.run(["open", str(polozky[i - 1]["subor"])])
            continue
        zmena = False
        for t in re.findall(r"[+-][\d-]+", cmd.replace(" ", " ")):
            for i in cisla(t[1:], len(polozky)):
                vyber[polozky[i - 1]["subor"].name] = t[0] == "+"
                zmena = True
        if zmena:
            uloz(); zobraz(polozky, vyber)
        else:
            print(f"Nerozumiem alebo číslo mimo 1–{len(polozky)}. Príklady: +9   -10   +3-7   o 9   z   t   q")


if __name__ == "__main__":
    main()
