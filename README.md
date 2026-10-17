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

## Čo nie je v repozitári
`secrets/`, `vstup/`, `vystup/`, všetky PDF, Excel a CSV súbory – výpisy a faktúry zostávajú len lokálne.

## Stav
- [x] Krok 0 – prostredie, prihlásenie do Gmailu
- [ ] Krok 1 – sťahovanie PDF z Gmailu
- [ ] Krok 2 – parser SLSP výpisu
- [ ] Krok 3 – extrakcia údajov z faktúr
- [ ] Krok 4 – párovanie + Excel
- [ ] Krok 5 – agent na nespárované položky
- [ ] Krok 6 – tlač, spúšťanie pri novom výpise
