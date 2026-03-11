"""
Locatie Info Module
Haalt actuele informatie op over een gemeente via gratis bronnen:
- Statbel (Belgisch statistiekbureau) voor bevolkingsdata
- Wikimedia voor algemene info
- Vastgoedprijzen via publieke bronnen
"""

import requests
import logging
import json

logger = logging.getLogger(__name__)


def haal_gemeente_info_op(gemeente: str, postcode: str) -> dict:
    """
    Haalt relevante info op over een gemeente voor vastgoedbeoordeling.
    Combineert meerdere gratis bronnen.
    """
    info = {
        "gemeente": gemeente,
        "postcode": postcode,
        "bevolking": None,
        "bevolkingsgroei": None,
        "mediaan_vastgoedprijs": None,
        "nabij_centrumstad": False,
        "centrumstad": None,
        "wikipedia_samenvatting": None,
        "fout": None,
    }

    # Stap 1: Wikipedia samenvatting ophalen
    try:
        wiki_url = f"https://nl.wikipedia.org/api/rest_v1/page/summary/{gemeente}"
        response = requests.get(wiki_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            samenvatting = data.get("extract", "")
            # Eerste 500 tekens — genoeg voor locatiecontext
            info["wikipedia_samenvatting"] = samenvatting[:500] if samenvatting else None
    except Exception as e:
        logger.debug(f"Wikipedia ophalen mislukt voor {gemeente}: {e}")

    # Stap 2: Check of gemeente nabij centrumstad ligt
    centrumsteden = {
        "Antwerpen": ["2000", "2018", "2020", "2030", "2040", "2050", "2060", "2100", "2140", "2150", "2170", "2180", "2600", "2610", "2660"],
        "Gent": ["9000", "9030", "9031", "9032", "9040", "9041", "9042", "9050", "9051", "9052"],
        "Mechelen": ["2800", "2801", "2811", "2812"],
        "Leuven": ["3000", "3001", "3010", "3012", "3018", "3020"],
        "Brussel": ["1000", "1020", "1030", "1040", "1050", "1060", "1070", "1080", "1081", "1082", "1083", "1090", "1140", "1150", "1160", "1170", "1180", "1190", "1200", "1210"],
        "Brugge": ["8000", "8020", "8200"],
        "Hasselt": ["3500", "3501", "3510"],
        "Kortrijk": ["8500", "8501", "8510"],
        "Aalst": ["9300", "9308"],
        "Roeselare": ["8800"],
    }

    for stad, postcodes in centrumsteden.items():
        if postcode in postcodes or gemeente.lower() == stad.lower():
            info["nabij_centrumstad"] = True
            info["centrumstad"] = stad
            break

    # Stap 3: Statbel bevolkingsdata (Belgisch statistiekbureau - open data)
    try:
        # Statbel open data API voor bevolking per gemeente
        statbel_url = f"https://statbel.fgov.be/sites/default/files/files/opendata/bevolking/population_{postcode}.json"
        response = requests.get(statbel_url, timeout=8)
        if response.status_code == 200:
            data = response.json()
            info["bevolking"] = data.get("population", None)
    except Exception:
        pass  # Statbel API is niet altijd beschikbaar, geen probleem

    # Stap 4: Gemiddelde vastgoedprijzen via Statbel open data
    try:
        # Statbel heeft open data over vastgoedtransacties per gemeente
        url = "https://statbel.fgov.be/sites/default/files/files/opendata/Vastgoedstatistieken/vastgoed_gemeente.json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Zoek de gemeente in de data
            for item in data:
                if str(item.get("postcode", "")) == str(postcode):
                    info["mediaan_vastgoedprijs"] = item.get("mediaan_prijs_woning", None)
                    info["bevolking"] = item.get("bevolking", info["bevolking"])
                    break
    except Exception:
        pass

    return info


def formatteer_locatie_context(info: dict) -> str:
    """
    Zet de locatie info om naar een leesbare tekst voor de AI prompt.
    """
    lijnen = []

    if info.get("nabij_centrumstad"):
        lijnen.append(f"CENTRUMSTAD: {info['gemeente']} is een centrumstad of ligt nabij {info['centrumstad']} - POSITIEF voor vastgoed")
    else:
        lijnen.append(f"LOCATIE: {info['gemeente']} ({info['postcode']}) - geen grote centrumstad")

    if info.get("bevolking"):
        lijnen.append(f"Bevolking: {info['bevolking']:,} inwoners")

    if info.get("mediaan_vastgoedprijs"):
        lijnen.append(f"Mediaan vastgoedprijs in gemeente: EUR {info['mediaan_vastgoedprijs']:,}")

    if info.get("wikipedia_samenvatting"):
        lijnen.append(f"Gemeenteinfo: {info['wikipedia_samenvatting']}")

    return "\n".join(lijnen) if lijnen else f"Gemeente: {info['gemeente']} ({info['postcode']})"
