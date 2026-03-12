"""
Harde Uitsluitregels — Directe REJECT voorwaarden
Als één van deze vlaggen aanwezig is → pand direct afwijzen, geen verdere analyse.

Bronnen: Immoweb data + wat we kunnen afleiden uit beschikbare velden.
In de toekomst uitbreiden met echte Geopunt/Kadaster API's.
"""

import logging

logger = logging.getLogger(__name__)

# Belgische beschermde gebieden / Natura2000 postcodes (vereenvoudigd - echte data via Geopunt API)
# Dit zijn voorbeeldpostcodes van bekende Natura2000 zones in België
NATURA2000_POSTCODES = {
    "9185",  # Drongen - Gentbrugse Meersen
    "2400",  # Mol - Kalmthoutse Heide omgeving
    "8690",  # Westkust - IJzerbroeken
    "3798",  # Voeren - Voerstreek
    "6640",  # Ardenne - Haute-Sûre
}

# Bekende historische overstromingsgebieden (Sigmaplan zones)
OVERSTROMINGS_POSTCODES = {
    "9140",  # Temse - Scheldevallei
    "9150",  # Kruibeke - overstromingsgebied
    "9130",  # Beveren - Waasland
    "2830",  # Rupelmonde
    "9100",  # Sint-Niklaas rand
}

# Industriële voormalige sites (verhoogd risico chemische verontreiniging)
INDUSTRIELE_TREFWOORDEN = [
    "industriezone", "fabriek", "werkplaats", "loods", "magazijn",
    "garage", "benzinestation", "droogkuis", "chemisch", "stookolietank"
]


def check_harde_regels(pand: dict, metrics: dict) -> tuple[bool, list]:
    """
    Controleert alle harde uitsluitregels.
    Geeft (heeft_rode_vlag: bool, lijst_van_vlaggen) terug.
    Als heeft_rode_vlag = True → direct REJECT.
    """
    vlaggen = []
    postcode = str(pand.get("postcode", ""))
    prijs = pand.get("prijs", 0) or 0
    perceel_opp = pand.get("perceel_opp", 0) or 0
    beschrijving = (pand.get("beschrijving", "") or "").lower()
    subtype = (pand.get("subtype", "") or "").lower()
    staat = (pand.get("staat", "") or "").lower()

    # ── 1. Natura2000 / beschermd natuurgebied ──────────────────────────
    if postcode in NATURA2000_POSTCODES:
        vlaggen.append("natura2000")
        logger.debug(f"Rode vlag: Natura2000 zone (postcode {postcode})")

    # ── 2. Kritisch overstromingsgebied ─────────────────────────────────
    if postcode in OVERSTROMINGS_POSTCODES:
        vlaggen.append("overstromingsgebied")
        logger.debug(f"Rode vlag: overstromingsgebied (postcode {postcode})")

    # ── 3. Geen bouwpotentieel (te klein perceel, geen woonbestemming) ──
    if perceel_opp > 0 and perceel_opp < 100:
        vlaggen.append("perceel_te_klein")
        logger.debug(f"Rode vlag: perceel {perceel_opp}m2 is te klein voor ontwikkeling")

    # ── 4. Prijs 0 of onrealistisch ─────────────────────────────────────
    if prijs <= 0:
        vlaggen.append("geen_prijs")

    if prijs > 0 and prijs < 10_000:
        vlaggen.append("onrealistische_prijs")

    # ── 5. Chemische verontreiniging / industrieel risico ───────────────
    for trefwoord in INDUSTRIELE_TREFWOORDEN:
        if trefwoord in beschrijving or trefwoord in subtype:
            vlaggen.append(f"industrieel_risico:{trefwoord}")
            logger.debug(f"Rode vlag: industrieel risico trefwoord '{trefwoord}'")
            break  # 1 vlag volstaat

    # ── 6. Financiële haalbaarheid absoluut onmogelijk ──────────────────
    project_marge = metrics.get("project_marge", 0)
    bruto_rendement = metrics.get("bruto_rendement", 0)
    prijs_per_m2_perceel = metrics.get("prijs_per_m2_perceel", 0)

    if project_marge < -30:  # Meer dan 30% verlies = absurd
        vlaggen.append("negatieve_marge_kritisch")

    if bruto_rendement > 0 and bruto_rendement < 1.0:
        vlaggen.append("rendement_absurd_laag")

    if prijs_per_m2_perceel > 3000:  # EUR 3000/m2 perceel = nooit rendabel
        vlaggen.append("perceel_prijs_te_hoog")

    heeft_rode_vlag = len(vlaggen) > 0
    return heeft_rode_vlag, vlaggen


def check_zachte_vlaggen(pand: dict, metrics: dict) -> list:
    """
    Zachte waarschuwingen — geen REJECT maar wel vermelden in rapport.
    """
    vlaggen = []
    bouwjaar = pand.get("bouwjaar", 0) or 0
    epc_waarde = pand.get("epc_waarde", 0) or 0
    perceel_opp = pand.get("perceel_opp", 0) or 0
    beschrijving = (pand.get("beschrijving", "") or "").lower()

    if bouwjaar > 0 and bouwjaar < 1950:
        vlaggen.append("oud_pand_voor_1950")  # Verhoogd risico asbest

    if epc_waarde > 800:
        vlaggen.append("zeer_slechte_epc")

    if "asbest" in beschrijving:
        vlaggen.append("asbest_vermeld")

    if "erfpacht" in beschrijving or "opstalrecht" in beschrijving:
        vlaggen.append("erfpacht_of_opstalrecht")  # Controleren door jurist

    if perceel_opp > 0 and perceel_opp < 250:
        vlaggen.append("perceel_krap")  # Weinig ontwikkelingsruimte

    return vlaggen
