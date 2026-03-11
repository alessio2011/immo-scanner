"""
IMMO SCANNER - Hoofdscript
Draait dag en nacht op de Raspberry Pi.

Werking:
- Elke 30 min: Immoweb scrapen → nieuwe panden in wachtrij
- Elke cyclus: kijk hoeveel tokens over → analyseer zoveel als past
- Trechtersysteem: goedkope check eerst, dure analyse alleen als nodig
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
import config2
from scrapers.immoweb import haal_advertenties_op, verwerk_pand
from analysis.berekeningen import bereken_metrics, is_interessant
from analysis.ai_analyse import analyseer_pand_met_ai
from analysis.token_tracker import tokens_in_laatste_minuut, tokens_vandaag, budget_status
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
    """Haalt nieuwe panden op en zet interessante in de wachtrij."""
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
    bestaande_ids = {item["pand_id"] for item in wachtrij}

    for pand_data in panden:
        pand_id = str(pand_data.get("id", ""))
        if not pand_id or pand_id in geziene_ids or pand_id in bestaande_ids:
            continue

        geziene_ids.add(pand_id)
        nieuwe += 1

        try:
            pand = verwerk_pand(pand_data)
            metrics = bereken_metrics(pand)
            interessant, _ = is_interessant(metrics, config.MIN_RENDEMENT)

            if interessant:
                wachtrij.append({
                    "pand_id": pand_id,
                    "pand": pand,
                    "metrics": metrics,
                    "score": metrics.get("interessantheid_score", 0),
                    "toegevoegd": datetime.now().isoformat()
                })
                toegevoegd += 1
                logger.info(f"  ➕ {pand.get('gemeente')} €{pand.get('prijs', 0):,} (score {metrics.get('interessantheid_score', 0)})")

        except Exception as e:
            logger.error(f"Fout bij verwerken {pand_id}: {e}")

    # Sorteer wachtrij op score — beste panden eerst
    if config2.PRIORITEER_WACHTRIJ:
        wachtrij.sort(key=lambda x: x.get("score", 0), reverse=True)

    logger.info(f"✅ Scrape klaar: {nieuwe} nieuw, {toegevoegd} toegevoegd, {len(wachtrij)} in wachtrij")
    return geziene_ids, wachtrij


# ─── STAP 2: SLIM AI BUDGET BEHEER ───────────────────────────────────────────

def hoeveel_analyses_mogelijk() -> int:
    """
    Kijkt hoeveel tokens er over zijn en schat hoeveel analyses nog passen.
    Een volledige analyse kost ~2700 tokens (alle stappen samen).
    """
    minuut_over = config2.TOKENS_PER_MINUUT_LIMIET - tokens_in_laatste_minuut()
    dag_over = config2.TOKENS_PER_DAG_LIMIET - tokens_vandaag()

    tokens_per_analyse = (
        config2.TOKENS_SNELLE_CHECK +
        config2.TOKENS_LOCATIE_CHECK +
        config2.TOKENS_FOTO_ANALYSE +
        config2.TOKENS_VOLLEDIGE_AI
    )

    # Hoeveel passen er in de minuut? En hoeveel zijn er nog over voor vandaag?
    mogelijk_minuut = int(minuut_over * 0.80 / tokens_per_analyse)  # 80% van over
    mogelijk_dag    = int(dag_over / tokens_per_analyse)

    aantal = min(mogelijk_minuut, mogelijk_dag, 3)  # Max 3 tegelijk
    return max(0, aantal)


def analyseer_batch(wachtrij: list, aantal: int) -> list:
    """Analyseert een batch van panden uit de wachtrij."""
    if not wachtrij or aantal == 0:
        return wachtrij

    logger.info(f"🤖 Batch analyse: {aantal} pand(en) van {len(wachtrij)} in wachtrij")

    for _ in range(min(aantal, len(wachtrij))):
        if not wachtrij:
            break

        item = wachtrij.pop(0)
        pand    = item["pand"]
        metrics = item["metrics"]
        pand_id = item["pand_id"]

        logger.info(f"🔬 Analyseren: {pand.get('gemeente')} €{pand.get('prijs', 0):,}")

        try:
            ai_analyse = analyseer_pand_met_ai(pand, metrics, config.ANTHROPIC_API_KEY)
            aanbeveling = ai_analyse.get("aanbeveling", "NEUTRAAL")

            if aanbeveling in ["STERK_AAN", "AAN"]:
                logger.info(f"  🔥 {aanbeveling} prio {ai_analyse.get('prioriteit')}/10 → melding!")
                sla_pand_op_voor_feedback(pand_id, pand, metrics, ai_analyse)
                stuur_melding(pand, metrics, ai_analyse, config)
            else:
                logger.info(f"  ➡️  {aanbeveling} → geen melding")

        except Exception as e:
            logger.error(f"Fout bij analyse {pand_id}: {e}")
            wachtrij.insert(0, item)  # Terug in wachtrij bij fout
            break

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

    geziene_ids  = laad_geziene_panden()
    wachtrij     = laad_wachtrij()
    logger.info(f"📋 {len(geziene_ids)} panden al gezien, {len(wachtrij)} in wachtrij")

    scan_interval  = getattr(config, 'SCAN_INTERVAL_MINUTEN', 30) * 60
    laatste_scrape = 0
    cyclus         = 0

    while True:
        nu = time.time()
        cyclus += 1

        # ── Feedback verwerken ──────────────────────────────────────────
        try:
            for pid, feedback in verwerk_feedback_updates(config):
                data = haal_pand_op_voor_feedback(pid)
                if data:
                    sla_feedback_op(data["pand"], data["metrics"], data["ai_analyse"], feedback)
                    logger.info(f"👍/👎 Feedback: {feedback} voor {pid}")
        except Exception as e:
            logger.error(f"Feedback fout: {e}")

        # ── Scrape nieuwe panden (elke 30 min) ─────────────────────────
        if nu - laatste_scrape >= scan_interval:
            try:
                geziene_ids, wachtrij = scrape_nieuwe_panden(geziene_ids, wachtrij)
                sla_geziene_panden_op(geziene_ids)
                sla_wachtrij_op(wachtrij)
                laatste_scrape = nu
            except Exception as e:
                logger.error(f"Scrape fout: {e}")

        # ── AI analyses — zoveel als het budget toelaat ─────────────────
        if wachtrij:
            aantal = hoeveel_analyses_mogelijk()
            if aantal > 0:
                try:
                    wachtrij = analyseer_batch(wachtrij, aantal)
                    sla_wachtrij_op(wachtrij)
                except Exception as e:
                    logger.error(f"Analyse fout: {e}")
            else:
                logger.info(f"⏳ Token budget te laag voor analyse — wachten...")

        # ── Status log elke 10 cycli ────────────────────────────────────
        if cyclus % 10 == 0:
            status = budget_status(config2.TOKENS_PER_MINUUT_LIMIET, config2.TOKENS_PER_DAG_LIMIET)
            logger.info(
                f"📊 Status | Wachtrij: {len(wachtrij)} | "
                f"Tokens dag: {status['dag_gebruikt']:,} ({status['dag_pct']}%) | "
                f"Aanroepen: {status['aanroepen_vandaag']}"
            )

        time.sleep(30)


if __name__ == "__main__":
    main()
