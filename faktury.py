"""
Faktúrový agent – všetko jedným príkazom.

    python faktury.py              # predchádzajúci mesiac: sken → sťahovanie → vyčítanie → výber a tlač
    python faktury.py 2026-09      # konkrétny mesiac
    python faktury.py --bez-gmailu # nesťahuje z Gmailu, len vyčíta a ide na výber
    python faktury.py --tlac       # rovno výber a tlač

Oranžová obrazovka = pracujem sám, zelená = čakám na teba.
"""
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import tema

BASE = Path(__file__).resolve().parent


def mesiac_z_argumentov():
    for a in sys.argv[1:]:
        if re.fullmatch(r"\d{4}-\d{2}", a):
            return a
    prvy = date.today().replace(day=1)
    return f"{(prvy - timedelta(days=1)):%Y-%m}"


def spusti(skript, mesiac):
    r = subprocess.run([sys.executable, str(BASE / skript), mesiac])
    if r.returncode != 0:
        tema.koniec()
        sys.exit(f"\nX {skript} skončil chybou – zastavujem. Výstup vyššie.")


def main():
    mesiac = mesiac_z_argumentov()
    args = sys.argv[1:]
    kroky = []
    if "--tlac" not in args:
        if "--bez-gmailu" not in args:
            kroky += [("Sken Gmailu", "1_gmail_scan.py"), ("Sťahovanie faktúr a výpisov", "2_stiahni.py")]
        kroky += [("Vyčítanie údajov (Claude)", "3_vycitaj.py")]

    try:
        if kroky:
            tema.obrazovka(tema.ORANZOVA)
            print(f"{tema.TUCNE}FAKTÚROVÝ AGENT · podklady za {mesiac}{tema.RESET}{tema.ORANZOVA}")
            for i, (nazov, skript) in enumerate(kroky, 1):
                tema.faza(nazov, i, len(kroky))
                spusti(skript, mesiac)
            input(f"\n{tema.TUCNE}Hotovo. Enter = pokračovať na výber a tlač…{tema.RESET}{tema.ORANZOVA}")
        spusti("tlac.py", mesiac)
    except KeyboardInterrupt:
        print("\nPrerušené.")
    finally:
        tema.koniec()


if __name__ == "__main__":
    main()
