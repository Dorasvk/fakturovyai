"""Nastavenia agenta – upravuj tu."""

# Kľúčové slová (hľadajú sa v predmete aj tele mailu; Gmail ignoruje veľkosť písmen)
KLUCOVE_SLOVA = [
    "faktúra", "faktura", "faktúru", "fakturu", "faktúry", "faktury",
    "invoice", "vyúčtovanie", "vyuctovanie", "daňový doklad", "danovy doklad",
    "zálohová", "zalohova", "dobropis", "doklad o platbe", "receipt",
    "payment confirmation", "potvrdenie platby", "potvrdenie objednávky",
    "e-faktúra", "efaktura", "rezervácia", "reservation", "booking confirmation",
]

# Známi dodávatelia – stačí časť adresy alebo domény odosielateľa
ZNAMI_ODOSIELATELIA = [
    "mcnet", "omv", "telekom", "alza", "booking.com", "pelikan",
]

# Typy príloh, ktoré môžu byť faktúra
PRILOHY = ["pdf", "isdoc", "xml", "zip"]
