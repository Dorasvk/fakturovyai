"""Nastavenia agenta – upravuj tu."""

# Kľúčové slová (hľadajú sa v predmete aj tele mailu; Gmail ignoruje veľkosť písmen)
KLUCOVE_SLOVA = [
    "faktúra", "faktura", "faktúru", "fakturu", "faktúry", "faktury",
    "invoice", "vyúčtovanie", "vyuctovanie", "daňový doklad", "danovy doklad",
    "zálohová", "zalohova", "dobropis", "doklad o platbe", "receipt",
    "payment confirmation", "potvrdenie platby", "potvrdenie objednávky",
    "e-faktúra", "efaktura", "rezervácia", "reservation", "booking confirmation",
    "doklad", "účtenka", "uctenka", "your receipt",
]

# Známi dodávatelia – stačí časť adresy alebo domény odosielateľa
ZNAMI_ODOSIELATELIA = [
    "mcnet", "omv", "telekom", "alza", "booking.com", "pelikan",
    "anthropic", "openai", "stripe",
]

# Typy príloh, ktoré môžu byť faktúra
PRILOHY = ["pdf", "isdoc", "xml", "zip"]

# Odosielatelia, ktorých úplne ignorujeme (časť adresy alebo domény)
IGNOROVANI_ODOSIELATELIA = [
    "swan.sk", "4ka.sk",
]

# === TLAČ ===
TLACIAREN = "HP7C4D8F865DEA__HP_Color_Laser_MFP_178_179__2"
# TLACIAREN = "TOSHIBA_e_STUDIO3505AC_11984160"

# Dodávatelia, ktorých faktúry tlačíme CELÉ (inak len 1. strana)
TLAC_CELE = ["omv.com"]

# Voľby tlače: čiernobielo, jednostranne
TLAC_VOLBY = ["-o", "print-color-mode=monochrome", "-o", "ColorModel=Gray", "-o", "sides=one-sided"]

# Ktoré súbory brať od daného dodávateľa (regex na názov súboru; ostatné sa ignorujú)
# platí pre prílohy aj pre súbory rozbalené zo ZIP
LEN_SUBORY = {
    "omv.com": r"_NI\.(pdf|xml)$",   # XML sa netlačí, pomôže pri vyčítaní údajov
}

# === VYČÍTANIE ÚDAJOV (Claude API) ===
MOJE_ICO = "46494677"            # Consult IT Pro s.r.o. – podľa toho rozlíšime vydané/prijaté
MODEL_EXTRAKCIA = "claude-sonnet-5-5"
MAX_STRAN_NA_EXTRAKCIU = 4       # z dlhých PDF (rozpis hovorov…) posielame len prvé strany
# Hraničné faktúry: DZP v nasledujúcom mesiaci do tohto dňa a obdobie plnenia zasahuje do mesiaca -> ❓ tlačiť
HRANICA_DNI = 10

# Vzhľad výberu v Termináli: "zeleny" (old-school fosfor) alebo "normal"
TEMA = "zeleny"

# Odtiene zelenej pri výbere (256-farebná paleta terminálu; 46 = klasický fosfor)
FARBA_VYBRANE = 46     # označené na tlač (tučne)
FARBA_NEVYBRANE = 28   # neoznačené (tmavšie)
FARBA_TEXT = 40        # hlavička a ostatný text

# === VÝPIS: platby bez dokladu ===
# Platby, ktoré doklad nepotrebujú (regex v type/popise/protistrane, bez ohľadu na veľkosť písmen)
IGNOROVAT_PLATBY = [
    r"výber", r"transakčná daň", r"poplatok", r"transakcie_\d+",
    r"sociáln\w* poisťov", r"socpoist", r"v[sš]zp", r"zdravotn\w* poisťov",
]
# Rada, kde doklad zohnať (regex na protistranu/obchodníka -> text)
NAPOVEDA = {
    r"microsoft": "faktúra Microsoft 365: admin.microsoft.com → Fakturácia → Faktúry",
    r"openai|chatgpt": "OpenAI: ChatGPT → Settings → Subscription / platform.openai.com → Billing → Invoices",
    r"contabo": "Contabo: my.contabo.com → Invoices",
    r"hetzner": "Hetzner: accounts.hetzner.com → Invoices",
    r"booking|bkg\*": "Booking: potvrdenie / faktúra od ubytovania alebo požičovne",
    r"dalnicka|edalnice": "CZ diaľničná známka: edalnice.cz → doklad o zaplatení",
    r"o2 slovakia": "O2: moje.o2.sk → Faktúry",
    r"shell|omv \d|slovnaft|orlen|mol ": "bloček z čerpacej stanice",
    r"park|parking|wiener|linien|ride": "bloček / potvrdenie (parkovanie, MHD)",
}
