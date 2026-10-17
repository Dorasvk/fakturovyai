"""Farby terminálu – old-school monochróm. Oranžová = pracujem, zelená = čakám na teba."""
import os
import sys

import config

ZAPNUTE = getattr(config, "TEMA", "normal") == "zeleny" and sys.stdout.isatty()
_256 = "256" in os.environ.get("TERM", "") or os.environ.get("COLORTERM")

ORANZOVA = ("\033[38;5;214;48;5;16m" if _256 else "\033[33;40m") if ZAPNUTE else ""
ZELENA = ("\033[38;5;46;48;5;16m" if _256 else "\033[32;40m") if ZAPNUTE else ""
TUCNE = "\033[1m" if ZAPNUTE else ""
TLMENE = "\033[2m" if ZAPNUTE else ""
RESET = "\033[0m" if ZAPNUTE else ""


def obrazovka(farba):
    """Prefarbí celé okno (pozadie čierne, písmo farbou)."""
    if ZAPNUTE:
        sys.stdout.write(farba + "\033[2J\033[H")
        sys.stdout.flush()


def faza(nazov, cislo=None, spolu=None):
    if ZAPNUTE:
        sys.stdout.write(ORANZOVA)
    poradie = f"[{cislo}/{spolu}] " if cislo else ""
    ciara = "═" * (len(poradie + nazov) + 4)
    print(f"\n{TUCNE}╔{ciara}╗\n║  {poradie}{nazov}  ║\n╚{ciara}╝{RESET}{ORANZOVA}")


def koniec():
    if ZAPNUTE:
        sys.stdout.write(RESET + "\n")
        sys.stdout.flush()
