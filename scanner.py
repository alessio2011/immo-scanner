"""
IMMO SCANNER - Hoofdscript
Draait automatisch op de Raspberry Pi en scant Immoweb
"""

import sys
import os
import time
import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path

# Voeg project root toe aan path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from scrapers.immoweb import haal_advertenties_op, verwerk_pand
from analysis.berekeningen import bereken_metrics, is_interessant
from analysis.ai_analyse import analyseer_pand_met_ai
from notifications.telegram import stuur_melding, stuur_opstart_bericht

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("immo_scanner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Bestand om al geziene panden bij te houden
GEZIEN_BESTAND = Path("geziene_panden.json")


def laad_geziene_panden() -> set:
    """Laadt de lijst van al geziene pand IDs."""
    if GEZIEN_BESTAND.exists():
        with open(GEZIEN_BESTAND, "r") as f:
            data = json.load(f)
            return set(data.get("ids", []))
    return set()


def sla_geziene_panden_op(ids: set):
    """Slaat de lijst van geziene pand IDs op."""
    with open(GEZIEN_BESTAND, "w") as f:
        json.dump({"ids": list(ids), "laatste_update": datetime.now().isoformat()}, f)


def verwerk_nieuwe_panden(geziene_ids: set) -> set:
    """
    Haalt nieuwe panden op, analyseert ze en stuurt meldingen.
    Geeft de bijgewerkte set van geziene IDs terug.
    """
    logger.info("🔍 Scanning Immoweb...")

    # Postcodes ophalen (of leeg = heel België)
    postcodes = config.REGIO_POSTCODES if config.REGIO_POSTCODES else [None]

    panden = haal_advertenties_op(
        postcodes=postcodes,
        max_prijs=config.MAX_PRIJS,
        min_prijs=config.MIN_PRIJS
    )

    logger.info(f"📦 {len(panden)} panden gevonden, filteren...")

    nieuwe_panden = 0
    interessante_panden = 0

    for pand_data in panden:
        pand_id = str(pand_data.get("id", ""))

        if not pand_id or pand_id in geziene_ids:
            continue

        geziene_ids.add(pand_id)
        nieuwe_panden += 1

        try:
            # Verwerk pand data
            pand = verwerk_pand(pand_data)

            # Bereken financiële metrics
            metrics = bereken_metrics(pand)

            # Voorcheck: is het potentieel interessant?
            interessant, redenen = is_interessant(metrics, config.MIN_RENDEMENT)

            if not interessant:
                logger.debug(f"❌ Niet interessant: {pand.get('gemeente')} - €{pand.get('prijs', 0):,}")
                continue

            logger.info(f"🎯 Potentieel interessant gevonden: {pand.get('gemeente')} - €{pand.get('prijs', 0):,}")

            # AI analyse (alleen voor potentieel interessante panden - bespaart API kosten)
            ai_analyse = analyseer_pand_met_ai(pand, metrics, config.ANTHROPIC_API_KEY)

            aanbeveling = ai_analyse.get("aanbeveling", "NEUTRAAL")

            if aanbeveling in ["STERK_AAN", "AAN"]:
                interessante_panden += 1
                logger.info(f"✅ AI zegt: {aanbeveling} - Melding versturen...")
                stuur_melding(pand, metrics, ai_analyse, config)
                time.sleep(3)  # Kleine pauze tussen berichten

        except Exception as e:
            logger.error(f"Fout bij verwerken pand {pand_id}: {e}")

    logger.info(f"✅ Scan klaar: {nieuwe_panden} nieuwe panden, {interessante_panden} interessant")
    return geziene_ids


def main():
    """Hoofdlus van de scanner."""
    logger.info("=" * 50)
    logger.info("🏠 IMMO SCANNER GESTART")
    logger.info("=" * 50)

    # Valideer configuratie
    if config.TELEGRAM_BOT_TOKEN == "UW_BOT_TOKEN_HIER":
        logger.error("❌ Telegram token niet ingesteld in config.py!")
        print("\n⚠️  Stel eerst uw tokens in in config.py")
        print("   Zie SETUP.md voor instructies")
        sys.exit(1)

    # Opstart bericht
    stuur_opstart_bericht(config)

    # Laad eerder geziene panden
    geziene_ids = laad_geziene_panden()
    logger.info(f"📋 {len(geziene_ids)} panden al eerder gezien")

    scan_interval = config.SCAN_INTERVAL_MINUTEN * 60

    # Eerste scan onmiddellijk
    try:
        geziene_ids = verwerk_nieuwe_panden(geziene_ids)
        sla_geziene_panden_op(geziene_ids)
    except Exception as e:
        logger.error(f"Fout bij eerste scan: {e}")

    # Herhalende scans
    while True:
        logger.info(f"⏳ Volgende scan over {config.SCAN_INTERVAL_MINUTEN} minuten...")
        time.sleep(scan_interval)

        try:
            geziene_ids = verwerk_nieuwe_panden(geziene_ids)
            sla_geziene_panden_op(geziene_ids)
        except KeyboardInterrupt:
            logger.info("🛑 Scanner gestopt door gebruiker")
            break
        except Exception as e:
            logger.error(f"Fout bij scan: {e}")
            time.sleep(60)  # Wacht 1 minuut bij fout


if __name__ == "__main__":
    main()
