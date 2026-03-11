"""
Immoweb Scraper
Haalt automatisch vastgoedadvertenties op van Immoweb
"""

import requests
import json
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

IMMOWEB_API = "https://www.immoweb.be/en/search/house,apartment/for-sale"
IMMOWEB_DETAIL_API = "https://www.immoweb.be/en/classified"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "nl-BE,nl;q=0.9",
    "Referer": "https://www.immoweb.be/",
}


def haal_advertenties_op(postcodes: list, max_prijs: int, min_prijs: int, max_paginas: int = 10) -> list:
    """
    Haalt advertenties op van Immoweb voor gegeven postcodes en prijsrange.
    Scrapet meerdere pagina's (standaard 10 = ~300 panden).
    """
    alle_panden = []

    if not postcodes:
        postcodes = [None]

    for postcode in postcodes:
        pagina = 1
        while pagina <= max_paginas:
            params = {
                "countries": "BE",
                "maxPrice": max_prijs,
                "minPrice": min_prijs,
                "orderBy": "newest",
                "page": pagina,
                "isAPublicSale": "false",
            }

            if postcode:
                params["postalCodes"] = postcode

            try:
                response = requests.get(
                    "https://www.immoweb.be/en/search-results/house,apartment/for-sale",
                    params=params,
                    headers=HEADERS,
                    timeout=15
                )

                if response.status_code == 200:
                    data = response.json()
                    resultaten = data.get("results", [])

                    if not resultaten:
                        # Geen resultaten meer op deze pagina → stoppen
                        logger.info(f"Postcode {postcode}: pagina {pagina} leeg, stoppen")
                        break

                    logger.info(f"Postcode {postcode}: pagina {pagina} → {len(resultaten)} panden")
                    alle_panden.extend(resultaten)

                    # Als er minder dan 30 resultaten zijn, is dit de laatste pagina
                    if len(resultaten) < 30:
                        break

                    pagina += 1
                else:
                    logger.warning(f"Immoweb fout: {response.status_code} voor postcode {postcode} pagina {pagina}")
                    break

                time.sleep(2)  # Beleefd wachten

            except Exception as e:
                logger.error(f"Fout bij ophalen Immoweb data pagina {pagina}: {e}")
                break

    logger.info(f"Totaal {len(alle_panden)} panden opgehaald")
    return alle_panden


def haal_detail_op(classified_id: int) -> dict:
    """
    Haalt volledige details op van een specifieke advertentie.
    """
    try:
        url = f"https://www.immoweb.be/en/classified/{classified_id}"
        response = requests.get(url, headers=HEADERS, timeout=15)

        if response.status_code == 200:
            # Immoweb embed JSON data in de HTML pagina
            import re
            match = re.search(r'window\.classified\s*=\s*(\{.*?\});', response.text, re.DOTALL)
            if match:
                return json.loads(match.group(1))

    except Exception as e:
        logger.error(f"Fout bij ophalen detail {classified_id}: {e}")

    return {}


def verwerk_pand(pand_data: dict) -> dict:
    """
    Zet ruwe Immoweb data om naar een gestandaardiseerd formaat.
    """
    property_data = pand_data.get("property", {})
    transaction = pand_data.get("transaction", {})
    location = property_data.get("location", {})

    prijs = transaction.get("sale", {}).get("price", 0)
    if not prijs:
        prijs = pand_data.get("price", {}).get("mainValue", 0)

    return {
        "id": pand_data.get("id", ""),
        "url": f"https://www.immoweb.be/en/classified/{pand_data.get('id', '')}",
        "titel": pand_data.get("title", "Geen titel"),
        "prijs": prijs,
        "type": property_data.get("type", ""),
        "subtype": property_data.get("subtype", ""),
        "slaapkamers": property_data.get("bedroomCount", 0),
        "bewoonbare_opp": property_data.get("netHabitableSurface", 0),
        "perceel_opp": property_data.get("landSurface", 0),
        "gemeente": location.get("locality", ""),
        "postcode": location.get("postalCode", ""),
        "straat": location.get("street", ""),
        "huisnummer": location.get("number", ""),
        "bouwjaar": property_data.get("constructionYear", None),
        "epc_score": property_data.get("EPCScore", ""),
        "epc_waarde": property_data.get("primaryEnergyConsumptionPerSqm", 0),
        "staat": property_data.get("condition", ""),
        "tuin": property_data.get("hasGarden", False),
        "garage": property_data.get("parkingCountOutdoor", 0) + property_data.get("parkingCountIndoor", 0),
        "publicatie_datum": pand_data.get("publicationDate", ""),
        "foto_url": pand_data.get("media", {}).get("pictures", [{}])[0].get("largeUrl", "") if pand_data.get("media", {}).get("pictures") else "",
        "alle_fotos": [p.get("largeUrl", "") for p in pand_data.get("media", {}).get("pictures", [])[:4] if p.get("largeUrl")],
    }
