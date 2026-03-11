"""
Financiële Berekeningsmodule
Berekent rendement, ontwikkelingspotentieel en andere metrics
"""

import logging

logger = logging.getLogger(__name__)

# Gemiddelde huurprijzen per m² per maand in België (schatting)
GEMIDDELDE_HUURPRIJS_PER_M2 = {
    "default": 10.0,    # €/m²/maand
    "antwerpen": 13.0,
    "gent": 12.0,
    "mechelen": 11.0,
    "brussel": 14.0,
    "leuven": 12.5,
}

# Gemiddelde renovatie/sloopkosten per m²
KOSTEN_PER_M2 = {
    "renovatie_licht": 300,      # Lichte renovatie
    "renovatie_zwaar": 800,      # Zware renovatie
    "sloop_nieuwbouw": 1500,     # Sloop + nieuwbouw
    "appartementen_nieuwbouw": 1800,  # Nieuwbouw appartementsblok
}

# Notaris- en registratiekosten in België
AANKOOPKOSTEN_PERCENT = 0.12    # ~12% boven op aankoopprijs (notaris + registratie)


def bereken_metrics(pand: dict) -> dict:
    """
    Berekent alle financiële en projectontwikkelingsmetrics voor een pand.
    """
    prijs = pand.get("prijs", 0) or 0
    bewoonbare_opp = pand.get("bewoonbare_opp", 0) or 0
    perceel_opp = pand.get("perceel_opp", 0) or 0
    gemeente = pand.get("gemeente", "").lower()

    # Basischeck
    if prijs == 0:
        return {"fout": "Geen prijs beschikbaar"}

    # --- PRIJS PER M² ---
    prijs_per_m2 = round(prijs / bewoonbare_opp, 2) if bewoonbare_opp > 0 else 0
    prijs_per_m2_perceel = round(prijs / perceel_opp, 2) if perceel_opp > 0 else 0

    # --- TOTALE AANKOOPKOST ---
    totale_aankoopkost = round(prijs * (1 + AANKOOPKOSTEN_PERCENT))

    # --- HUURRENDEMENT SCHATTING ---
    huurprijs_per_m2 = GEMIDDELDE_HUURPRIJS_PER_M2.get(gemeente, GEMIDDELDE_HUURPRIJS_PER_M2["default"])
    geschatte_huur_maand = round(bewoonbare_opp * huurprijs_per_m2) if bewoonbare_opp > 0 else 0
    geschatte_huur_jaar = geschatte_huur_maand * 12
    bruto_rendement = round((geschatte_huur_jaar / prijs) * 100, 2) if prijs > 0 else 0
    netto_rendement = round(bruto_rendement * 0.7, 2)  # ~30% kosten (beheer, leestand, onderhoud)

    # --- SLOOP & HERBOUW POTENTIEEL ---
    # Schat hoeveel appartementen passen op het perceel
    if perceel_opp > 0:
        # Gemiddeld 80m² bewoonbaar per appartement, bouwindex 2.0 (2x perceel)
        max_bouwvolume = perceel_opp * 2.0
        geschat_aantal_appartementen = max(1, int(max_bouwvolume / 80))
        gemiddelde_verkoopprijs_app = 250_000  # Schatting nieuwbouw appartement
        geschatte_verkoopopbrengst = geschat_aantal_appartementen * gemiddelde_verkoopprijs_app

        # Kosten sloop + nieuwbouw
        sloopkosten = round(perceel_opp * 30)  # ~€30/m² sloop
        nieuwbouwkosten = round(max_bouwvolume * KOSTEN_PER_M2["appartementen_nieuwbouw"])
        totale_projectkosten = totale_aankoopkost + sloopkosten + nieuwbouwkosten

        project_winst = geschatte_verkoopopbrengst - totale_projectkosten
        project_marge = round((project_winst / totale_projectkosten) * 100, 1) if totale_projectkosten > 0 else 0
    else:
        geschat_aantal_appartementen = 0
        geschatte_verkoopopbrengst = 0
        sloopkosten = 0
        nieuwbouwkosten = 0
        totale_projectkosten = 0
        project_winst = 0
        project_marge = 0

    # --- RENOVATIE POTENTIEEL ---
    epc_waarde = pand.get("epc_waarde", 0) or 0
    renovatie_nodig = epc_waarde > 300 or pand.get("staat", "") in ["TO_RENOVATE", "TO_BE_DONE_UP"]

    if renovatie_nodig and bewoonbare_opp > 0:
        renovatiekost = round(bewoonbare_opp * KOSTEN_PER_M2["renovatie_zwaar"])
    elif bewoonbare_opp > 0:
        renovatiekost = round(bewoonbare_opp * KOSTEN_PER_M2["renovatie_licht"])
    else:
        renovatiekost = 0

    totaal_na_renovatie = totale_aankoopkost + renovatiekost

    # --- INTERESSANTHEID SCORE (0-100) ---
    score = 0

    if bruto_rendement >= 7:
        score += 30
    elif bruto_rendement >= 5:
        score += 20
    elif bruto_rendement >= 3:
        score += 10

    if project_marge >= 20:
        score += 30
    elif project_marge >= 10:
        score += 20
    elif project_marge >= 5:
        score += 10

    if perceel_opp >= 500:
        score += 20
    elif perceel_opp >= 300:
        score += 10

    if prijs_per_m2 > 0 and prijs_per_m2 < 1500:
        score += 20
    elif prijs_per_m2 < 2000:
        score += 10

    return {
        # Basis
        "prijs": prijs,
        "totale_aankoopkost": totale_aankoopkost,
        "prijs_per_m2": prijs_per_m2,
        "prijs_per_m2_perceel": prijs_per_m2_perceel,

        # Verhuur
        "geschatte_huur_maand": geschatte_huur_maand,
        "geschatte_huur_jaar": geschatte_huur_jaar,
        "bruto_rendement": bruto_rendement,
        "netto_rendement": netto_rendement,

        # Projectontwikkeling
        "geschat_aantal_appartementen": geschat_aantal_appartementen,
        "geschatte_verkoopopbrengst": geschatte_verkoopopbrengst,
        "sloopkosten": sloopkosten,
        "nieuwbouwkosten": nieuwbouwkosten,
        "totale_projectkosten": totale_projectkosten,
        "project_winst": project_winst,
        "project_marge": project_marge,

        # Renovatie
        "renovatie_nodig": renovatie_nodig,
        "renovatiekost": renovatiekost,
        "totaal_na_renovatie": totaal_na_renovatie,

        # Score
        "interessantheid_score": min(100, score),
    }


def is_interessant(metrics: dict, min_rendement: float = 5.0) -> tuple[bool, list]:
    """
    Bepaalt of een pand interessant is en waarom.
    Geeft (True/False, [redenen]) terug.
    """
    redenen = []

    if metrics.get("fout"):
        return False, []

    score = metrics.get("interessantheid_score", 0)
    bruto_rendement = metrics.get("bruto_rendement", 0)
    project_marge = metrics.get("project_marge", 0)
    perceel_opp = metrics.get("prijs_per_m2_perceel", 0)

    if bruto_rendement >= min_rendement:
        redenen.append(f"✅ Goed huurrendement: {bruto_rendement}% bruto")

    if project_marge >= 15:
        redenen.append(f"✅ Sterke projectmarge: {project_marge}%")
    elif project_marge >= 8:
        redenen.append(f"⚠️ Redelijke projectmarge: {project_marge}%")

    if metrics.get("geschat_aantal_appartementen", 0) >= 4:
        redenen.append(f"✅ Groot perceel: geschikt voor {metrics['geschat_aantal_appartementen']} appartementen")

    if metrics.get("prijs_per_m2", 0) < 1500 and metrics.get("prijs_per_m2", 0) > 0:
        redenen.append(f"✅ Lage prijs per m²: €{metrics['prijs_per_m2']}/m²")

    return score >= 40 and len(redenen) > 0, redenen
