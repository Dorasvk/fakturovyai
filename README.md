# Faktúrový AI agent

Párovanie faktúr z Gmailu s pohybmi na účte (SLSP výpis v PDF).
Hybrid: pevná pipeline (sťahovanie, parsovanie, párovanie podľa VS a sumy) + AI agent na dohľadanie nespárovaných položiek.

**Gmail je pripojený len na čítanie (`gmail.readonly`)** – skript nič neodosiela ani nemaže.

## Rozbehnutie na novom počítači (macOS, Apple Silicon)

```bash
git clone git@github.com:Dorasvk/fakturovyai.git faktury-agent
cd faktury-agent
CONDA_SUBDIR=osx-arm64 conda create -n faktury python=3.12 -y
conda activate faktury
conda config --env --set subdir osx-arm64
pip install -r requirements.txt
mkdir -p secrets vstup vystup
```

Do `secrets/` treba ručne doplniť (nie sú v gite):
- `credentials.json` – OAuth klient (Desktop app) z Google Cloud projektu s Gmail API, scope `gmail.readonly`
- neskôr API kľúč Claude

Test prihlásenia:
```bash
python 0_test_gmail.py
```

## Použitie (mesačne)

```bash
conda activate faktury
cd ~/faktury-agent
python faktury.py              # predchádzajúci mesiac – všetko jedným príkazom
python faktury.py 2026-09      # konkrétny mesiac
python faktury.py --bez-gmailu # bez sťahovania, len vyčítanie + výber
python faktury.py --tlac       # rovno výber a tlač
```
Oranžová obrazovka = agent pracuje sám, zelená = čaká na teba (výber šípkami, medzera, Enter = náhľad, t = tlač, q = koniec).

Nastavenia (dodávatelia, ignorovaní, tlačiareň, čo tlačiť celé, farby): `config.py`.
Heslo k ZIP výpisom SLSP: `secrets/zip_hesla.txt`. API kľúč Claude: `secrets/anthropic_key.txt`.

## Čo nie je v repozitári
`secrets/`, `vstup/`, `vystup/`, všetky PDF, Excel a CSV súbory – výpisy a faktúry zostávajú len lokálne.

## Stav
- [x] Krok 0 – prostredie, prihlásenie do Gmailu
- [x] Krok 1 – sken Gmailu so skórovaním
- [x] Krok 2 – sťahovanie faktúr, rozbaľovanie ZIP
- [x] Krok 3 – vyčítanie údajov (Claude API), DZP, duplicity
- [x] Tlač – výber v termináli, 1. strana / celé, otočenie na výšku
- [ ] Krok 4 – výpis SLSP + párovanie, platby bez faktúry, výnimky
- [ ] Krok 5 – agent na nespárované položky
- [ ] Pekné GUI
