"""
IMMO SCANNER - Hoofdscript
Draait dag en nacht op de Raspberry Pi.

Werking:
- Elke 30 min: Immoweb scrapen → nieuwe panden in wachtrij
- Elke 60 sec: 1 pand uit wachtrij analyseren met AI → nooit rate limit
- Feedback van Telegram knoppen verwerken bij elke cyclus
"""

import sys
import os
import time
import json
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from scrapers.immoweb import haal_advertenties_op, verwerk_pand
from analysis.berekeningen import bereken_metrics, is_interessant
from analysis.ai_analyse import analyseer_pand_met_ai
from notifications.telegram import stuur_melding, stuur_opstart_bericht, verwerk_feedback_updates
from analysis.feedback import sla_pand_op_voor_feedback, haal_pand_op_voor_feedback, sla_feedback_op

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("immo_scanner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

GEZIEN_BESTAND   = Path("geziene_panden.json")
WACHTRIJ_BESTAND = Path("ai_wachtrij.json")


# ─── HULPFUNCTIES ────────────────────────────────────────────────────────────

def laad_geziene_panden() -> set:
    if GEZIEN_BESTAND.exists():
        with open(GEZIEN_BESTAND) as f:
            return set(json.load(f).get("ids", []))
    return set()

def sla_geziene_panden_op(ids: set):
    with open(GEZIEN_BESTAND, "w") as f:
        json.dump({"ids": list(ids), "update": datetime.now().isoformat()}, f)

def laad_wachtrij() -> list:
    if WACHTRIJ_BESTAND.exists():
        with open(WACHTRIJ_BESTAND) as f:
            return json.load(f)
    return []

def sla_wachtrij_op(wachtrij: list):
    with open(WACHTRIJ_BESTAND, "w") as f:
        json.dump(wachtrij, f, ensure_ascii=False)


# ─── STAP 1: SCRAPEN ─────────────────────────────────────────────────────────

def scrape_nieuwe_panden(geziene_ids: set, wachtrij: list) -> tuple[set, list]:
    """
    Haalt nieuwe panden op van Immoweb en zet interessante in de AI wachtrij.
    Dit is snel en gebruikt geen AI tokens.
    """
    logger.info("🔍 Immoweb scrapen...")

    postcodes = config.REGIO_POSTCODES if config.REGIO_POSTCODES else [None]
    panden = haal_advertenties_op(
        postcodes=postcodes,
        max_prijs=config.MAX_PRIJS,
        min_prijs=config.MIN_PRIJS,
        max_paginas=getattr(config, 'MAX_PAGINAS', 10)
    )

    nieuwe = 0
    toegevoegd = 0

    for pand_data in panden:
        pand_id = str(pand_data.get("id", ""))
        if not pand_id or pand_id in geziene_ids:
            continue

        geziene_ids.add(pand_id)
        nieuwe += 1

        try:
            pand = verwerk_pand(pand_data)
            metrics = bereken_metrics(pand)
            interessant, _ = is_interessant(metrics, config.MIN_RENDEMENT)

            if interessant:
                # Zet in wachtrij voor AI analyse later
                wachtrij.append({
                    "pand_id": pand_id,
                    "pand": pand,
                    "metrics": metrics,
                    "toegevoegd": datetime.now().isoformat()
                })
                toegevoegd += 1
                logger.info(f"➕ Wachtrij: {pand.get('gemeente')} €{pand.get('prijs', 0):,}")

        except Exception as e:
            logger.error(f"Fout bij verwerken pand {pand_id}: {e}")

    logger.info(f"✅ Scrape klaar: {nieuwe} nieuw, {toegevoegd} in wachtrij (totaal: {len(wachtrij)})")
    return geziene_ids, wachtrij


# ─── STAP 2: AI ANALYSE (1 PER CYCLUS) ───────────────────────────────────────

def analyseer_volgend_pand(wachtrij: list) -> list:
    """
    Haalt 1 pand uit de wachtrij en analyseert die met AI.
    Door 1 per minuut te doen vermijden we de rate limit volledig.
    """
    if not wachtrij:
        return wachtrij

    item = wachtrij.pop(0)  # Eerste uit de rij
    pand    = item["pand"]
    metrics = item["metrics"]
    pand_id = item["pand_id"]

    logger.info(f"🤖 AI analyse: {pand.get('gemeente')} €{pand.get('prijs', 0):,} ({len(wachtrij)} nog in wachtrij)")

    try:
        ai_analyse = analyseer_pand_met_ai(pand, metrics, config.ANTHROPIC_API_KEY)
        aanbeveling = ai_analyse.get("aanbeveling", "NEUTRAAL")

        if aanbeveling in ["STERK_AAN", "AAN"]:
            logger.info(f"✅ {aanbeveling} → melding sturen!")
            sla_pand_op_voor_feedback(pand_id, pand, metrics, ai_analyse)
            stuur_melding(pand, metrics, ai_analyse, config)
        else:
            logger.info(f"❌ AI: {aanbeveling} → geen melding")

    except Exception as e:
        logger.error(f"Fout bij AI analyse: {e}")
        # Bij fout terug in wachtrij zetten
        wachtrij.insert(0, item)
        time.sleep(30)  # Extra wachten bij fout

    return wachtrij


# ─── HOOFDLUS ─────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 50)
    logger.info("🏠 IMMO SCANNER GESTART")
    logger.info("=" * 50)

    if config.TELEGRAM_BOT_TOKEN == "UW_BOT_TOKEN_HIER":
        logger.error("❌ Telegram token niet ingesteld in config.py!")
        sys.exit(1)

    stuur_opstart_bericht(config)

    geziene_ids = laad_geziene_panden()
    wachtrij    = laad_wachtrij()
    logger.info(f"📋 {len(geziene_ids)} panden al gezien, {len(wachtrij)} in wachtrij")

    scan_interval   = getattr(config, 'SCAN_INTERVAL_MINUTEN', 30) * 60
    ai_interval     = 60   # 1 AI analyse per minuut → nooit rate limit
    laatste_scrape  = 0    # Zorgt dat eerste scrape meteen gebeurt
    laatste_ai      = 0

    while True:
        nu = time.time()

        # ── Feedback verwerken ──────────────────────────────────────────
        try:
            feedback_updates = verwerk_feedback_updates(config)
            for pid, feedback in feedback_updates:
                data = haal_pand_op_voor_feedback(pid)
                if data:
                    sla_feedback_op(data["pand"], data["metrics"], data["ai_analyse"], feedback)
                    logger.info(f"Feedback: {feedback} voor pand {pid}")
        except Exception as e:
            logger.error(f"Fout bij feedback: {e}")

        # ── Scrape nieuwe panden (elke 30 min) ─────────────────────────
        if nu - laatste_scrape >= scan_interval:
            try:
                geziene_ids, wachtrij = scrape_nieuwe_panden(geziene_ids, wachtrij)
                sla_geziene_panden_op(geziene_ids)
                sla_wachtrij_op(wachtrij)
                laatste_scrape = nu
            except Exception as e:
                logger.error(f"Fout bij scrapen: {e}")

        # ── AI analyse (1 per minuut) ───────────────────────────────────
        if nu - laatste_ai >= ai_interval and wachtrij:
            try:
                wachtrij = analyseer_volgend_pand(wachtrij)
                sla_wachtrij_op(wachtrij)
                laatste_ai = nu
            except Exception as e:
                logger.error(f"Fout bij AI analyse: {e}")

        # ── Status log elke 10 min ──────────────────────────────────────
        if len(wachtrij) > 0:
            logger.info(f"⏳ Wachtrij: {len(wachtrij)} panden te analyseren")

        time.sleep(30)  # Elke 30 seconden de lus doorlopen


if __name__ == "__main__":
    main()