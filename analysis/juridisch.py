"""
Juridische Verkenning Module — Stap 5
Alleen voor panden die GO of REVIEW halen.

Stap 1: Data verzamelen via Geopunt API (stedenbouwkundige bestemming)
Stap 2: AI analyseert bestemming + optop/splitsen haalbaarheid
Stap 3: Rendementberekening optop-scenario
Stap 4: Advies notaris / landmeter

Kost: ~800-1000 tokens (krachtig model)
"""

import requests
import json
import logging

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Geopunt WFS endpoint voor bestemmingen (AGIV)
GEOPUNT_WFS = "https://geo.api.vlaanderen.be/GRB/wfs"
GEOPUNT_OMGEVINGSINFO = "https://omgevingsloket.omgeving.vlaanderen.be/publiek/omgevingsinfo"

# Nieuwbouwprijzen per regio (EUR/m², bron: CIB 2024)
NIEUWBOUW_PRIJZEN_M2 = {
    "antwerpen": 4200, "gent": 4000, "brussel": 4500, "leuven": 4100,
    "mechelen": 3600, "brugge": 3800, "kortrijk": 3200, "aalst": 3000,
    "hasselt": 3200, "genk": 2900, "sint-truiden": 2700, "tongeren": 2700,
    "lommel": 2800, "neerpelt": 2700, "hamont": 2600,
    "default": 2800
}

# Optoppen bouwkosten (EUR/m² bruto vloeroppervlak)
OPTOPPEN_BOUWKOST_M2 = 2400   # inclusief stabiliteitswerken, architect, BTW, EPB
OPTOPPEN_KOST_VAST   = 25000  # vaste kost: stabiliteitsstudie, vergunning, notaris

# Gemiddelde appartement bij optoppen
OPTOPPEN_APP_OPP_M2  = 80     # netto bewoonbaar

# Verhuur referentieprijzen (EUR/m²/maand)
HUUR_M2_MAAND = {
    "antwerpen": 13.5, "gent": 13.0, "brussel": 15.0, "leuven": 14.0,
    "mechelen": 11.0, "brugge": 11.5, "hasselt": 9.5, "genk": 8.5,
    "sint-truiden": 8.0, "tongeren": 8.0,
    "default": 8.5
}


def _ai_call_juridisch(prompt: str, api_key: str, model: str, max_tokens: int = 800) -> str:
    """
    AI call voor juridische analyse.
    Detecteert automatisch of Gemini of Groq gebruikt wordt op basis van het model.
    """
    # Gemini model → gebruik Gemini API
    if model in ("gemini", "gemini-2.0-flash", "gemini-1.5-flash"):
        try:
            from analysis.gemini_analyse import gemini_juridisch_call
            return gemini_juridisch_call(prompt, api_key)
        except Exception as e:
            logger.error(f"Gemini juridisch fout: {e}")
            return ""

    # Groq model → gebruik Groq API
    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": 0.1,
                "messages": [
                    {"role": "system", "content": "Je bent een Belgische stedenbouwkundige expert. Antwoord altijd in geldig JSON."},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            logger.warning(f"Groq juridisch: HTTP {response.status_code}")
            return ""
    except Exception as e:
        logger.error(f"Groq juridisch fout: {e}")
        return ""


def _parse_json(tekst: str) -> dict:
    if "```" in tekst:
        tekst = tekst.split("```")[1]
        if tekst.startswith("json"):
            tekst = tekst[4:]
    try:
        return json.loads(tekst.strip())
    except Exception:
        return {}


def haal_geopunt_bestemming(gemeente: str, postcode: str, straat: str, huisnummer: str) -> dict:
    """
    Haalt stedenbouwkundige info op via Geopunt geocoder + bestemmingskaart.
    Geeft dict terug met beschikbare data, of lege dict bij fout.
    """
    resultaat = {
        "adres_gevonden": False,
        "bestemming_raw": "",
        "gewest_plan": "",
        "rup_naam": "",
        "lat": None,
        "lon": None,
    }

    # Stap 1: Geocoding via Geopunt
    try:
        adres_query = f"{straat} {huisnummer}, {postcode} {gemeente}"
        r = requests.get(
            "https://geo.api.vlaanderen.be/geolocation/v4/Location",
            params={"q": adres_query, "c": 1, "type": "crab_address"},
            timeout=8
        )
        if r.status_code == 200:
            data = r.json()
            locaties = data.get("LocationResult", [])
            if locaties:
                loc = locaties[0]
                resultaat["adres_gevonden"] = True
                resultaat["lat"] = loc.get("Location", {}).get("Lat_WGS84")
                resultaat["lon"] = loc.get("Location", {}).get("Lon_WGS84")
                logger.debug(f"  Geopunt geocode: {resultaat['lat']}, {resultaat['lon']}")
    except Exception as e:
        logger.debug(f"  Geopunt geocode fout: {e}")

    # Stap 2: Bestemmingskaart via AGIV WMS (als we coördinaten hebben)
    if resultaat["lat"] and resultaat["lon"]:
        try:
            # Gewestplan bestemming via REST
            r2 = requests.get(
                "https://geo.api.vlaanderen.be/QRGP/wfs",
                params={
                    "SERVICE": "WFS",
                    "VERSION": "2.0.0",
                    "REQUEST": "GetFeature",
                    "TYPENAMES": "QRGP:QRGP",
                    "CQL_FILTER": f"INTERSECTS(SHAPE,POINT({resultaat['lon']} {resultaat['lat']}))",
                    "OUTPUTFORMAT": "application/json",
                    "COUNT": "1"
                },
                timeout=8
            )
            if r2.status_code == 200:
                gj = r2.json()
                features = gj.get("features", [])
                if features:
                    props = features[0].get("properties", {})
                    resultaat["gewest_plan"] = props.get("BESTEMMING", "") or props.get("LABEL", "")
                    resultaat["bestemming_raw"] = json.dumps(props, ensure_ascii=False)[:500]
                    logger.debug(f"  Gewestplan: {resultaat['gewest_plan']}")
        except Exception as e:
            logger.debug(f"  Gewestplan WFS fout: {e}")

    return resultaat


def bereken_optop_scenario(pand: dict, metrics: dict) -> dict:
    """
    Berekent de financiële haalbaarheid van optoppen.
    Residuele waarde methode: V - (C + P) = R
    """
    gemeente = pand.get("gemeente", "").lower()
    perceel_opp = pand.get("perceel_opp", 0) or 0
    bewoonbare_opp = pand.get("bewoonbare_opp", 0) or 0
    prijs = pand.get("prijs", 0) or 0

    # Aankoopkost
    aankoopkost = metrics.get("totale_aankoopkost", prijs * 1.12)

    # Verkoopprijs nieuwbouw
    prijs_m2_nw = NIEUWBOUW_PRIJZEN_M2.get(gemeente, NIEUWBOUW_PRIJZEN_M2["default"])

    # Schatting: 1 verdieping optoppen = perceel_opp * 0.4 bruto, of min 1 app van 80m²
    if perceel_opp > 0:
        bruto_optoppen = min(perceel_opp * 0.4, 200)  # max 200m² bruto extra
    else:
        bruto_optoppen = OPTOPPEN_APP_OPP_M2 * 1.2  # 1 app als fallback

    netto_optoppen = bruto_optoppen * 0.85  # gemeenschappelijke delen
    aantal_apps_optop = max(1, int(netto_optoppen / OPTOPPEN_APP_OPP_M2))

    # Exit-waarde (V)
    exit_waarde = netto_optoppen * prijs_m2_nw

    # Stichtingskosten (C) — bouwkost + vaste kosten
    bouwkost = bruto_optoppen * OPTOPPEN_BOUWKOST_M2
    totale_stichtingskosten = bouwkost + OPTOPPEN_KOST_VAST

    # Residuele waarde (R = V - C - aankoopkost)
    residuele_waarde = exit_waarde - totale_stichtingskosten - aankoopkost

    # Winstmarge bij verkoop
    totale_investering = aankoopkost + totale_stichtingskosten
    winstmarge_pct = round((residuele_waarde / totale_investering) * 100, 1) if totale_investering > 0 else 0

    # NAR bij verhuur van het optopappartement
    huur_m2 = HUUR_M2_MAAND.get(gemeente, HUUR_M2_MAAND["default"])
    maandhuur = netto_optoppen * huur_m2
    jaarhuur = maandhuur * 12
    nar = round((jaarhuur / (aankoopkost + totale_stichtingskosten)) * 100, 2) if (aankoopkost + totale_stichtingskosten) > 0 else 0

    return {
        "bruto_opp_extra_m2":     round(bruto_optoppen, 0),
        "netto_opp_extra_m2":     round(netto_optoppen, 0),
        "aantal_apps_optop":      aantal_apps_optop,
        "prijs_m2_nieuwbouw":     prijs_m2_nw,
        "exit_waarde":            round(exit_waarde, 0),
        "bouwkost":               round(bouwkost, 0),
        "vaste_kosten":           OPTOPPEN_KOST_VAST,
        "totale_stichtingskosten":round(totale_stichtingskosten, 0),
        "aankoopkost":            round(aankoopkost, 0),
        "totale_investering":     round(totale_investering, 0),
        "residuele_waarde":       round(residuele_waarde, 0),
        "winstmarge_pct":         winstmarge_pct,
        "maandhuur_optop":        round(maandhuur, 0),
        "jaarhuur_optop":         round(jaarhuur, 0),
        "nar_pct":                nar,
        "formule": f"R = V({round(exit_waarde):,}) - C({round(totale_stichtingskosten):,}) - P({round(aankoopkost):,}) = {round(residuele_waarde):,}"
    }


def juridische_ai_analyse(pand: dict, metrics: dict, geopunt_data: dict,
                           optop: dict, api_key: str, model: str) -> dict:
    """
    AI analyseert de juridische haalbaarheid op basis van alle verzamelde data.
    """
    gemeente = pand.get("gemeente", "?")
    postcode = pand.get("postcode", "?")
    straat = pand.get("straat", "?")
    huisnummer = pand.get("huisnummer", "")
    perceel = pand.get("perceel_opp", 0)
    bouwjaar = pand.get("bouwjaar", "?")

    gewest_plan = geopunt_data.get("gewest_plan", "onbekend")
    adres_gevonden = geopunt_data.get("adres_gevonden", False)
    bestemming_raw = geopunt_data.get("bestemming_raw", "")

    prompt = f"""Je bent een Belgische stedenbouwkundige expert gespecialiseerd in Vlaanderen.

Analyseer dit pand voor juridische haalbaarheid van OPTOPPEN of OPSPLITSEN:

ADRES: {straat} {huisnummer}, {postcode} {gemeente}
PERCEEL: {perceel}m² | BOUWJAAR: {bouwjaar}
GEWESTPLAN BESTEMMING (Geopunt): {gewest_plan if gewest_plan else "niet opgehaald"}
RAW DATA GEOPUNT: {bestemming_raw[:300] if bestemming_raw else "niet beschikbaar"}
ADRES GEOCODEERD: {'ja' if adres_gevonden else 'nee'}

OPTOP BEREKENING:
- Extra bruto m²: {optop['bruto_opp_extra_m2']}m²
- Exit-waarde (V): €{optop['exit_waarde']:,}
- Stichtingskosten (C): €{optop['totale_stichtingskosten']:,}
- Aankoopkost (P): €{optop['aankoopkost']:,}
- Residuele waarde (R): €{optop['residuele_waarde']:,}
- Winstmarge: {optop['winstmarge_pct']}%
- NAR bij verhuur: {optop['nar_pct']}%

Beoordeel:
1. Stedenbouwkundige bestemming: is optoppen/opsplitsen toegestaan?
2. RUP/BPA risico's: welke regels gelden typisch in {gemeente} voor meergezinswoningen?
3. Parkeer- en kwaliteitsvereisten voor dit type project
4. Is de winstmarge van {optop['winstmarge_pct']}% haalbaar na juridische kosten?
5. Rol notaris en landmeter (basisakte, kadastrale splitsing)

REGELS die ge moet kennen:
- Agrarisch gebied: optoppen/opsplitsen VERBODEN
- Landelijk woongebied: beperkt, max 2 wooneenheden
- Woongebied: optoppen/opsplitsen MOGELIJK, afhankelijk RUP
- Woonuitbreidingsgebied: beperkt, gemeentelijk RUP vereist
- Woonpark: opsplitsen vaak verboden

Antwoord ALLEEN in JSON:
{{
  "bestemming_label": "Woongebied",
  "bestemming_kleur": "groen",
  "optoppen_toegestaan": true,
  "opsplitsen_toegestaan": true,
  "juridisch_risico": "laag",
  "rup_aandacht": "Vraag RUP en stedenbouwkundig attest op bij gemeente",
  "parkeer_norm": "1 parkeerplaats per appartement vereist in {gemeente}",
  "gecoro_risico": "Geen specifieke beperkingen bekend voor deze zone",
  "notaris_taken": ["Basisakte opstellen", "Mede-eigendom regelen"],
  "landmeter_taken": ["Kadastrale splitsing", "Opmeting perceel", "Plannen tekenen"],
  "juridische_kost_schatting": 8500,
  "aanbeveling": "GO",
  "aanbeveling_uitleg": "Woongebied laat optoppen toe. Vraag stedenbouwkundig attest aan.",
  "stedenbouwkundig_attest_nodig": true,
  "doorlooptijd_vergunning_maanden": 6,
  "haalbaarheid_score": 75
}}

bestemming_kleur: groen (woongebied) / oranje (beperkt) / rood (verboden)
juridisch_risico: laag / gemiddeld / hoog
aanbeveling: GO / REVIEW / STOP"""

    tekst = _ai_call_juridisch(prompt, api_key, model, max_tokens=700)
    if not tekst:
        return _fallback_juridisch()

    resultaat = _parse_json(tekst)
    if not resultaat:
        return _fallback_juridisch()

    return resultaat


def _fallback_juridisch() -> dict:
    return {
        "bestemming_label": "Onbekend",
        "bestemming_kleur": "oranje",
        "optoppen_toegestaan": None,
        "opsplitsen_toegestaan": None,
        "juridisch_risico": "gemiddeld",
        "rup_aandacht": "Controleer RUP bij gemeente",
        "parkeer_norm": "Controleer gemeentelijk reglement",
        "gecoro_risico": "Onbekend",
        "notaris_taken": ["Basisakte opstellen", "Mede-eigendom regelen"],
        "landmeter_taken": ["Kadastrale splitsing", "Plannen tekenen"],
        "juridische_kost_schatting": 8000,
        "aanbeveling": "REVIEW",
        "aanbeveling_uitleg": "Juridische data niet beschikbaar — manueel controleren.",
        "stedenbouwkundig_attest_nodig": True,
        "doorlooptijd_vergunning_maanden": 6,
        "haalbaarheid_score": 50
    }


def voer_juridische_verkenning_uit(pand: dict, metrics: dict, api_key: str, model: str) -> dict:
    """
    Hoofdfunctie: voert de volledige juridische verkenning uit.
    Geeft een dict terug met alle juridische data + optop berekening.
    Kost: ~800-1000 tokens.
    """
    gemeente = pand.get("gemeente", "?")
    straat = pand.get("straat", "")
    huisnummer = pand.get("huisnummer", "")
    postcode = pand.get("postcode", "")

    logger.info(f"  ⚖️  Juridische verkenning: {straat} {huisnummer}, {gemeente}")

    # Stap 1: Geopunt data ophalen
    geopunt_data = haal_geopunt_bestemming(gemeente, postcode, straat, huisnummer)
    logger.info(f"  Geopunt: adres={'gevonden' if geopunt_data['adres_gevonden'] else 'niet gevonden'} | bestemming={geopunt_data.get('gewest_plan', '-')}")

    # Stap 2: Optop berekening
    optop = bereken_optop_scenario(pand, metrics)
    logger.info(f"  Optop: marge={optop['winstmarge_pct']}% | NAR={optop['nar_pct']}% | R=€{optop['residuele_waarde']:,}")

    # Stap 3: AI analyse
    ai_juridisch = juridische_ai_analyse(pand, metrics, geopunt_data, optop, api_key, model)
    logger.info(f"  Juridisch AI: {ai_juridisch.get('bestemming_label')} | {ai_juridisch.get('aanbeveling')} | score {ai_juridisch.get('haalbaarheid_score')}/100")

    return {
        "geopunt": geopunt_data,
        "optop_scenario": optop,
        "ai_beoordeling": ai_juridisch,
    }
