"""
Financiële Berekeningsmodule
Realistische berekeningen zoals een echte projectontwikkelaar dat doet.

BELANGRIJK - Hoe appartementen schatten werkt in werkelijkheid:
- Niet elke m2 perceel = bouwbaar
- Gemeenten leggen BOUWDICHTHEID op (bv. max 60% van perceel bebouwen)
- Gemeenten leggen AANTAL VERDIEPINGEN op (bv. max 3 verdiepingen)
- Een appartement is gemiddeld 85-100m2 bewoonbaar
- Je moet ook rekening houden met gemeenschappelijke delen, traphal, lift (~25% extra)
"""

import logging

logger = logging.getLogger(__name__)

# Realistische huurprijzen per m² per maand in België (2024-2025)
HUURPRIJS_PER_M2 = {
    "default": 9.0,
    "antwerpen": 13.5,
    "gent": 12.5,
    "mechelen": 11.0,
    "brussel": 15.0,
    "leuven": 13.0,
    "brugge": 11.0,
    "hasselt": 9.5,
    "kortrijk": 9.0,
    "aalst": 8.5,
    "roeselare": 8.0,
    "turnhout": 8.5,
    "genk": 8.5,
}

# Realistische bouwkosten per m² in België (2024-2025, incl. BTW 21%)
BOUWKOSTEN_PER_M2 = {
    "nieuwbouw_appartement": 2000,   # EUR/m² bewoonbaar (sleutelklaar)
    "sloop": 50,                      # EUR/m² perceeloppervlakte
    "renovatie_licht": 400,           # EUR/m² bewoonbaar (schilderwerk, keuken, badkamer)
    "renovatie_zwaar": 900,           # EUR/m² bewoonbaar (structureel, EPC verbetering)
    "renovatie_volledig": 1400,       # EUR/m² bewoonbaar (bijna nieuwbouw)
}

# Gemiddelde verkoopprijzen nieuwbouwappartementen per regio (2024-2025)
VERKOOPPRIJS_NIEUWBOUW = {
    "default": 280_000,
    "antwerpen": 380_000,
    "gent": 360_000,
    "mechelen": 320_000,
    "brussel": 420_000,
    "leuven": 370_000,
    "brugge": 330_000,
    "hasselt": 290_000,
    "kortrijk": 275_000,
    "aalst": 265_000,
}

AANKOOPKOSTEN_PERCENT = 0.12  # 12% notaris + registratierechten


def schat_appartementen_realistisch(perceel_opp: float, gemeente: str) -> dict:
    """
    Schat het aantal haalbare appartementen op een perceel.
    Rekening houdend met echte Belgische bouwregels.

    In werkelijkheid bepaalt de gemeente:
    - Bebouwingspercentage (hoeveel % van perceel mag bebouwd worden)
    - Max aantal bouwlagen
    - Minimale oppervlakte per appartement

    Zonder stedenbouwkundig attest kunnen we alleen schatten.
    """
    if perceel_opp <= 0:
        return {"aantal": 0, "uitleg": "Geen perceeldata"}

    gemeente_lower = gemeente.lower()

    # Realistische bebouwingspercentages per type gemeente
    # Centrumsteden laten meer toe dan landelijke gemeenten
    centrumsteden = ["antwerpen", "gent", "brussel", "mechelen", "leuven", "brugge", "hasselt", "kortrijk"]

    if gemeente_lower in centrumsteden:
        bebouwingspct = 0.60   # 60% van perceel bebouwbaar
        max_lagen = 4           # Gemiddeld 4 bouwlagen toegelaten
    else:
        bebouwingspct = 0.45   # 45% in kleinere gemeenten
        max_lagen = 3           # Gemiddeld 3 lagen

    # Bruto vloeroppervlakte (BVO) = bewoonbaar + gemeenschappelijke delen
    # Gemeenschappelijke delen = ~20% van BVO (traphal, lift, berging)
    bebouwbaar_opp = perceel_opp * bebouwingspct
    bruto_vloeropp = bebouwbaar_opp * max_lagen
    netto_woonoppervlakte = bruto_vloeropp * 0.80  # 80% is effectief woonruimte

    # Gemiddelde appartement in Vlaanderen = 90m² netto
    gem_opp_per_app = 90
    aantal = int(netto_woonoppervlakte / gem_opp_per_app)

    # Minimale perceelgrootte voor een appartementenproject
    if perceel_opp < 250:
        return {"aantal": 0, "uitleg": f"Perceel te klein ({perceel_opp}m2) voor appartementen"}
    if perceel_opp < 400:
        aantal = min(aantal, 4)  # Kleine percelen = max 4 apps realistisch
    if perceel_opp < 600:
        aantal = min(aantal, 8)

    return {
        "aantal": max(0, aantal),
        "bebouwbaar_opp": round(bebouwbaar_opp),
        "bruto_vloeropp": round(bruto_vloeropp),
        "bebouwingspct": bebouwingspct,
        "max_lagen": max_lagen,
        "uitleg": f"{bebouwingspct*100:.0f}% bebouwing, {max_lagen} lagen, ~{gem_opp_per_app}m2/app"
    }


def bereken_metrics(pand: dict) -> dict:
    """
    Berekent alle financiële en projectontwikkelingsmetrics voor een pand.
    Realistische berekeningen zoals een projectontwikkelaar dat doet.
    """
    prijs = pand.get("prijs", 0) or 0
    bewoonbare_opp = pand.get("bewoonbare_opp", 0) or 0
    perceel_opp = pand.get("perceel_opp", 0) or 0
    gemeente = pand.get("gemeente", "").lower()
    bouwjaar = pand.get("bouwjaar", 0) or 0
    epc_waarde = pand.get("epc_waarde", 0) or 0
    staat = pand.get("staat", "") or ""

    if prijs == 0:
        return {"fout": "Geen prijs beschikbaar"}

    # --- AANKOOPKOST ---
    totale_aankoopkost = round(prijs * (1 + AANKOOPKOSTEN_PERCENT))
    prijs_per_m2 = round(prijs / bewoonbare_opp, 0) if bewoonbare_opp > 0 else 0
    prijs_per_m2_perceel = round(prijs / perceel_opp, 0) if perceel_opp > 0 else 0

    # --- HUURRENDEMENT ---
    huurprijs_m2 = HUURPRIJS_PER_M2.get(gemeente, HUURPRIJS_PER_M2["default"])
    geschatte_huur_maand = round(bewoonbare_opp * huurprijs_m2) if bewoonbare_opp > 0 else 0
    geschatte_huur_jaar = geschatte_huur_maand * 12
    bruto_rendement = round((geschatte_huur_jaar / prijs) * 100, 1) if prijs > 0 else 0
    netto_rendement = round(bruto_rendement * 0.68, 1)  # ~32% kosten: 15% leegstand+onderhoud, 10% belastingen, 7% verzekering

    # --- RENOVATIESCENARIO ---
    # Bepaal staat van renovatie realistisch
    if staat in ["TO_RENOVATE", "TO_BE_DONE_UP"] or epc_waarde > 500:
        renovatie_type = "volledig"
        renovatiekost = round(bewoonbare_opp * BOUWKOSTEN_PER_M2["renovatie_volledig"]) if bewoonbare_opp > 0 else 0
    elif epc_waarde > 300 or (bouwjaar > 0 and bouwjaar < 1970):
        renovatie_type = "zwaar"
        renovatiekost = round(bewoonbare_opp * BOUWKOSTEN_PER_M2["renovatie_zwaar"]) if bewoonbare_opp > 0 else 0
    elif epc_waarde > 150:
        renovatie_type = "licht"
        renovatiekost = round(bewoonbare_opp * BOUWKOSTEN_PER_M2["renovatie_licht"]) if bewoonbare_opp > 0 else 0
    else:
        renovatie_type = "geen"
        renovatiekost = 0

    renovatie_nodig = renovatie_type in ["zwaar", "volledig"]
    totaal_na_renovatie = totale_aankoopkost + renovatiekost

    # --- SLOOP/HERBOUW SCENARIO ---
    app_schatting = schat_appartementen_realistisch(perceel_opp, gemeente)
    geschat_aantal_appartementen = app_schatting["aantal"]

    if geschat_aantal_appartementen > 0:
        verkoopprijs_per_app = VERKOOPPRIJS_NIEUWBOUW.get(gemeente, VERKOOPPRIJS_NIEUWBOUW["default"])
        geschatte_verkoopopbrengst = geschat_aantal_appartementen * verkoopprijs_per_app

        sloopkosten = round(perceel_opp * BOUWKOSTEN_PER_M2["sloop"])
        # Nieuwbouwkost op basis van bruto vloeroppervlakte
        bruto_vloeropp = app_schatting.get("bruto_vloeropp", geschat_aantal_appartementen * 110)
        nieuwbouwkosten = round(bruto_vloeropp * BOUWKOSTEN_PER_M2["nieuwbouw_appartement"])

        # Extra kosten: architect (8%), studiekosten, vergunning (3%), onvoorzien (5%)
        extra_kosten = round((sloopkosten + nieuwbouwkosten) * 0.16)

        totale_projectkosten = totale_aankoopkost + sloopkosten + nieuwbouwkosten + extra_kosten
        project_winst = geschatte_verkoopopbrengst - totale_projectkosten
        project_marge = round((project_winst / totale_projectkosten) * 100, 1) if totale_projectkosten > 0 else 0
    else:
        geschatte_verkoopopbrengst = 0
        sloopkosten = 0
        nieuwbouwkosten = 0
        totale_projectkosten = 0
        project_winst = 0
        project_marge = 0

    # --- INTERESSANTHEID SCORE (0-100) ---
    score = 0
    if bruto_rendement >= 7: score += 25
    elif bruto_rendement >= 5: score += 15
    elif bruto_rendement >= 3.5: score += 8

    if project_marge >= 20: score += 30
    elif project_marge >= 12: score += 20
    elif project_marge >= 6: score += 10

    if perceel_opp >= 600: score += 20
    elif perceel_opp >= 350: score += 12
    elif perceel_opp >= 250: score += 5

    if prijs_per_m2 > 0 and prijs_per_m2 < 1200: score += 15
    elif prijs_per_m2 < 1800: score += 8
    elif prijs_per_m2 < 2500: score += 3

    if geschat_aantal_appartementen >= 6: score += 10
    elif geschat_aantal_appartementen >= 3: score += 5

    return {
        "prijs": prijs,
        "totale_aankoopkost": totale_aankoopkost,
        "prijs_per_m2": prijs_per_m2,
        "prijs_per_m2_perceel": prijs_per_m2_perceel,
        "geschatte_huur_maand": geschatte_huur_maand,
        "geschatte_huur_jaar": geschatte_huur_jaar,
        "bruto_rendement": bruto_rendement,
        "netto_rendement": netto_rendement,
        "geschat_aantal_appartementen": geschat_aantal_appartementen,
        "app_schatting_uitleg": app_schatting.get("uitleg", ""),
        "geschatte_verkoopopbrengst": geschatte_verkoopopbrengst,
        "sloopkosten": sloopkosten,
        "nieuwbouwkosten": nieuwbouwkosten,
        "totale_projectkosten": totale_projectkosten,
        "project_winst": project_winst,
        "project_marge": project_marge,
        "renovatie_type": renovatie_type,
        "renovatie_nodig": renovatie_nodig,
        "renovatiekost": renovatiekost,
        "totaal_na_renovatie": totaal_na_renovatie,
        "interessantheid_score": min(100, score),
    }


def is_interessant(metrics: dict, min_rendement: float = 5.0) -> tuple[bool, list]:
    """Bepaalt of een pand de moeite waard is voor AI analyse."""
    redenen = []
    if metrics.get("fout"):
        return False, []

    score = metrics.get("interessantheid_score", 0)
    bruto_rendement = metrics.get("bruto_rendement", 0)
    project_marge = metrics.get("project_marge", 0)
    perceel_opp = metrics.get("prijs_per_m2_perceel", 0)

    # Ruimere drempels — de AI filtert daarna nog verder
    if bruto_rendement >= min_rendement:
        redenen.append(f"Goed huurrendement: {bruto_rendement}%")
    if bruto_rendement >= 3.5:  # Al interessant voor AI om te bekijken
        redenen.append(f"Redelijk rendement: {bruto_rendement}%")
    if project_marge >= 8:
        redenen.append(f"Projectmarge: {project_marge}%")
    if metrics.get("geschat_aantal_appartementen", 0) >= 2:
        redenen.append(f"Potentieel {metrics['geschat_aantal_appartementen']} appartementen")
    if metrics.get("prijs_per_m2", 0) < 1800 and metrics.get("prijs_per_m2", 0) > 0:
        redenen.append(f"Prijs/m2: EUR {metrics['prijs_per_m2']}")

    # Score 20 is al genoeg voor een AI check — liever te veel dan te weinig
    return score >= 20 and len(redenen) > 0, redenen
