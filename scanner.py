"""
IMMO SCANNER — Multi-user versie
Draait dag en nacht op de Raspberry Pi.

Werking:
- Scant GLOBAAL over de unie van alle user-postcodes
- Analyseert met Gemini AI (gratis, geen tokenlimieten)
- GO/REVIEW panden zichtbaar voor relevante users via website
- Telegram enkel voor ADMIN: GO panden, REVIEW panden (stil), fouten, dagrapport
- Gewone users: alleen website (en later app)
"""

import sys, os, time, json, logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config2
from scrapers.immoweb import haal_advertenties_op, verwerk_pand
from analysis.berekeningen import bereken_metrics, is_interessant
from analysis.gemini_analyse import analyseer_pand_met_gemini  # Primair: gratis
from analysis.ai_analyse import analyseer_pand_met_ai          # Fallback: Groq
from analysis.harde_regels import check_harde_regels, check_zachte_vlaggen
from analysis.scorekaart import voer_scorekaart_uit, bepaal_beslissing
from analysis.juridisch import voer_juridische_verkenning_uit
from analysis.feedback import sla_pand_op_voor_feedback, haal_pand_op_voor_feedback, sla_feedback_op
from notifications.telegram import (
    stuur_opstart_bericht, stuur_go_melding, stuur_review_melding,
    stuur_fout_melding, check_dagrapport, verwerk_feedback_updates_multi
)
from auth import _laad_users

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
PENDING_DIR      = Path("pending_feedback")
PENDING_DIR.mkdir(exist_ok=True)

# Config laden
try:
    import config as _cfg
    TELEGRAM_BOT_TOKEN = getattr(_cfg, "TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_ID  = getattr(_cfg, "TELEGRAM_CHAT_ID", "")
    GEMINI_API_KEY     = getattr(_cfg, "GEMINI_API_KEY", "")   # Primair
    GROQ_API_KEY       = getattr(_cfg, "ANTHROPIC_API_KEY", "") # Fallback (Groq key)
except Exception as e:
    logger.error(f"Config laden fout: {e}")
    TELEGRAM_BOT_TOKEN = TELEGRAM_ADMIN_ID = GEMINI_API_KEY = GROQ_API_KEY = ""

GEBRUIK_GEMINI = bool(GEMINI_API_KEY)  # Automatisch switchen


# ─── USERS ───────────────────────────────────────────────────────────────────

def haal_actieve_users() -> list:
    return list(_laad_users().values())

def haal_alle_postcodes(users: list) -> set:
    """Unie van alle postcodes van alle users — dit is wat globaal gescand wordt."""
    postcodes = set()
    for user in users:
        for pc in user.get("config", {}).get("postcodes", []):
            postcodes.add(str(pc))
    return postcodes

def is_admin(user: dict) -> bool:
    return user.get("rol") == "admin"


# ─── OPSLAG ──────────────────────────────────────────────────────────────────

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

def sla_pand_op_globaal(pand_id: str, pand: dict, metrics: dict, ai_analyse: dict):
    """Slaat pand op zodat alle users het kunnen zien via de API."""
    bestand = PENDING_DIR / f"{pand_id}.json"
    with open(bestand, "w", encoding="utf-8") as f:
        json.dump({
            "pand": pand, "metrics": metrics, "ai_analyse": ai_analyse,
            "opgeslagen": datetime.now().isoformat()
        }, f, ensure_ascii=False, indent=2)

def tel_resultaten_vandaag() -> dict:
    """Telt GO/REVIEW/REJECT van vandaag voor dagrapport."""
    vandaag = datetime.now().date().isoformat()
    go = review = 0
    for f in PENDING_DIR.glob("*.json"):
        if f.stat().st_mtime and datetime.fromtimestamp(f.stat().st_mtime).date().isoformat() == vandaag:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                beslissing = data.get("ai_analyse", {}).get("beslissing", "")
                if beslissing == "GO":    go += 1
                elif beslissing == "REVIEW": review += 1
            except Exception:
                pass
    gezien = laad_geziene_panden()
    return {"go": go, "review": review, "reject": max(0, len(gezien) - go - review),
            "gescand": len(gezien)}


# ─── SCRAPEN ─────────────────────────────────────────────────────────────────

def scrape_nieuwe_panden(geziene_ids: set, wachtrij: list, postcodes: set, users: list) -> tuple[set, list]:
    if not postcodes:
        logger.info("⏳ Geen postcodes — wachten op eerste gebruiker die onboarding doet...")
        return geziene_ids, wachtrij

    logger.info(f"🔍 Globaal scrapen: {len(postcodes)} postcodes")

    # Meest inclusief: hoogste max_prijs, laagste min_rendement van alle users
    max_prijs = max((u.get("config", {}).get("max_prijs", 600000) for u in users), default=600000)
    min_rend  = min((u.get("config", {}).get("min_rendement", 3.5) for u in users), default=3.5)

    panden = haal_advertenties_op(
        postcodes=list(postcodes),
        max_prijs=max_prijs,
        min_prijs=0,
        max_paginas=getattr(config2, "MAX_PAGINAS", 10)
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
            pand    = verwerk_pand(pand_data)
            metrics = bereken_metrics(pand)

            heeft_rode_vlag, rode_vlaggen = check_harde_regels(pand, metrics)
            if heeft_rode_vlag:
                logger.debug(f"  🚫 {rode_vlaggen} → skip {pand.get('gemeente')}")
                continue

            interessant, _ = is_interessant(metrics, min_rend)
            if interessant:
                wachtrij.append({
                    "pand_id": pand_id, "pand": pand, "metrics": metrics,
                    "score": metrics.get("interessantheid_score", 0),
                    "toegevoegd": datetime.now().isoformat()
                })
                toegevoegd += 1
                logger.info(f"  ➕ {pand.get('gemeente')} €{pand.get('prijs',0):,} (postcode {pand.get('postcode')})")

        except Exception as e:
            logger.error(f"Fout bij verwerken {pand_id}: {e}")

    if config2.PRIORITEER_WACHTRIJ:
        wachtrij.sort(key=lambda x: x.get("score", 0), reverse=True)

    logger.info(f"✅ Scrape: {nieuwe} nieuw, {toegevoegd} toegevoegd → wachtrij: {len(wachtrij)}")
    return geziene_ids, wachtrij


# ─── AI ANALYSE ──────────────────────────────────────────────────────────────

def analyseer_batch(wachtrij: list, users: list) -> list:
    """
    Analyseert panden met AI.
    Primair: Gemini Flash 2.0 (gratis, geen tokenlimieten)
    Fallback: Groq trechtersysteem (als Gemini key ontbreekt)

    GO/REVIEW → globaal opslaan + admin Telegram melding.
    Gewone users → zien het via website, geen Telegram.
    """
    if not wachtrij:
        return wachtrij
    if not GEMINI_API_KEY and not GROQ_API_KEY:
        logger.error("❌ Geen AI API key! Voeg GEMINI_API_KEY of ANTHROPIC_API_KEY toe aan config.py")
        return wachtrij

    # Max 5 per cyclus — Pi-vriendelijk
    aantal = min(len(wachtrij), 5)
    ai_naam = "Gemini" if GEBRUIK_GEMINI else "Groq"
    logger.info(f"🤖 {ai_naam} analyse: {aantal} panden")

    for _ in range(aantal):
        if not wachtrij:
            break

        item    = wachtrij.pop(0)
        pand    = item["pand"]
        metrics = item["metrics"]
        pand_id = item["pand_id"]
        gemeente = pand.get("gemeente", "?")

        logger.info(f"🔬 Analyseren: {gemeente} €{pand.get('prijs',0):,}")

        try:
            # ── AI analyse ────────────────────────────────────────────────
            if GEBRUIK_GEMINI:
                ai_analyse = analyseer_pand_met_gemini(pand, metrics, GEMINI_API_KEY)
                # Als Gemini mislukt, probeer Groq
                if ai_analyse.get("aanbeveling") == "NEUTRAAL" and "mislukt" in ai_analyse.get("korte_uitleg", ""):
                    if GROQ_API_KEY:
                        logger.info(f"  ↩️  Gemini mislukt — Groq fallback")
                        ai_analyse = analyseer_pand_met_ai(pand, metrics, GROQ_API_KEY)
            else:
                ai_analyse = analyseer_pand_met_ai(pand, metrics, GROQ_API_KEY)

            # ── Scorekaart ────────────────────────────────────────────────
            zachte_vlaggen = check_zachte_vlaggen(pand, metrics)
            scorekaart     = voer_scorekaart_uit(pand, metrics, zachte_vlaggen=zachte_vlaggen)
            totale_score   = scorekaart["totale_score"]
            beslissing, _  = bepaal_beslissing(totale_score, [], config2.DREMPEL_GO, config2.DREMPEL_REVIEW)

            ai_analyse["beslissing"]     = beslissing
            ai_analyse["totale_score"]   = totale_score
            ai_analyse["subscores"]      = scorekaart.get("subscores", {})
            ai_analyse["scenarios"]      = scorekaart.get("scenarios", {})
            ai_analyse["zachte_vlaggen"] = zachte_vlaggen

            if beslissing in ["GO", "REVIEW"]:
                logger.info(f"  {'🔥' if beslissing=='GO' else '👀'} {beslissing} | {totale_score}/100 | {gemeente}")

                # ── Juridische verkenning ─────────────────────────────────
                try:
                    jur_model = "gemini" if GEBRUIK_GEMINI else config2.GROQ_MODEL_KRACHTIG
                    jur_key   = GEMINI_API_KEY if GEBRUIK_GEMINI else GROQ_API_KEY
                    ai_analyse["juridisch"] = voer_juridische_verkenning_uit(
                        pand, metrics, jur_key, jur_model
                    )
                except Exception as e:
                    logger.warning(f"  Juridisch fout: {e}")
                    ai_analyse["juridisch"] = None

                # ── Globaal opslaan — zichtbaar voor alle users ───────────
                sla_pand_op_globaal(pand_id, pand, metrics, ai_analyse)
                sla_pand_op_voor_feedback(pand_id, pand, metrics, ai_analyse)

                # ── Admin Telegram melding ────────────────────────────────
                if TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID:
                    try:
                        if beslissing == "GO":
                            stuur_go_melding(pand, metrics, ai_analyse,
                                             TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, scorekaart=scorekaart)
                            logger.info(f"  📱 GO melding → admin")
                        else:
                            stuur_review_melding(pand, metrics, ai_analyse,
                                                 TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)
                            logger.info(f"  📱 REVIEW melding → admin (stil)")
                    except Exception as e:
                        logger.warning(f"  Telegram fout: {e}")
                # ── Gewone users: GEEN Telegram → alleen website ──────────

            else:
                logger.info(f"  ➡️  REJECT | {totale_score}/100 | {gemeente}")

            time.sleep(3)  # Pi-vriendelijk, Gemini rate limit respecteren

        except Exception as e:
            logger.error(f"Fout bij analyse {pand_id}: {e}")
            try:
                stuur_fout_melding(f"Analyse {pand_id}: {str(e)[:200]}", TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)
            except Exception:
                pass
            wachtrij.insert(0, item)
            break

    return wachtrij


# ─── HOOFDLUS ────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 55)
    logger.info("🏠 IMMOVATE — Multi-user | Admin-only Telegram")
    logger.info("=" * 55)

    if GEBRUIK_GEMINI:
        logger.info("🤖 AI: Gemini Flash 2.0 (gratis, geen tokenlimieten)")
        if GROQ_API_KEY:
            logger.info("   ↩️  Groq als fallback geconfigureerd")
    elif GROQ_API_KEY:
        logger.info("🤖 AI: Groq trechtersysteem (Gemini key niet gevonden)")
    else:
        logger.error("❌ Geen AI key gevonden!")
        logger.error("   Voeg toe aan config.py:")
        logger.error("   GEMINI_API_KEY = 'AIza...'  ← ophalen via aistudio.google.com")
        logger.error("   of ANTHROPIC_API_KEY = 'gsk_...'  ← Groq key")
        return

    if TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID:
        stuur_opstart_bericht(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)
        logger.info(f"📱 Telegram admin meldingen actief → {TELEGRAM_ADMIN_ID}")
    else:
        logger.warning("⚠️ Telegram niet geconfigureerd — geen admin meldingen")

    geziene_ids   = laad_geziene_panden()
    wachtrij      = laad_wachtrij()
    logger.info(f"📋 {len(geziene_ids)} panden al gezien | {len(wachtrij)} in wachtrij")

    scan_interval  = 30 * 60
    laatste_scrape = 0
    cyclus = 0

    while True:
        nu = time.time()
        cyclus += 1

        users     = haal_actieve_users()
        postcodes = haal_alle_postcodes(users)

        if cyclus == 1 or cyclus % 20 == 0:
            logger.info(f"👥 {len(users)} users | {len(postcodes)} postcodes in unie")

        # ── Feedback verwerken (Telegram knoppen) ─────────────────────────
        if TELEGRAM_BOT_TOKEN:
            try:
                for pid, feedback in verwerk_feedback_updates_multi(TELEGRAM_BOT_TOKEN):
                    data = haal_pand_op_voor_feedback(pid)
                    if data:
                        sla_feedback_op(data["pand"], data["metrics"], data["ai_analyse"], feedback)
                        logger.info(f"👍/👎 Feedback: {feedback} → {pid}")
            except Exception as e:
                logger.error(f"Feedback fout: {e}")

        # ── Scrape elke 30 minuten ────────────────────────────────────────
        if nu - laatste_scrape >= scan_interval:
            try:
                geziene_ids, wachtrij = scrape_nieuwe_panden(geziene_ids, wachtrij, postcodes, users)
                sla_geziene_panden_op(geziene_ids)
                sla_wachtrij_op(wachtrij)
                laatste_scrape = nu
            except Exception as e:
                logger.error(f"Scrape fout: {e}")
                stuur_fout_melding(f"Scrape fout: {str(e)[:200]}", TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)

        # ── AI analyses ───────────────────────────────────────────────────
        if wachtrij:
            try:
                wachtrij = analyseer_batch(wachtrij, users)
                sla_wachtrij_op(wachtrij)
            except Exception as e:
                logger.error(f"Analyse fout: {e}")
                stuur_fout_melding(f"Analyse crash: {str(e)[:200]}", TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)

        # ── Dagrapport (18u, automatisch) ─────────────────────────────────
        if TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID:
            try:
                stats = tel_resultaten_vandaag()
                stats["users"]    = len(users)
                stats["postcodes"]= len(postcodes)
                stats["wachtrij"] = len(wachtrij)
                check_dagrapport(stats, TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID)
            except Exception:
                pass

        # ── Status log ────────────────────────────────────────────────────
        if cyclus % 10 == 0:
            logger.info(f"📊 Cyclus {cyclus} | Wachtrij: {len(wachtrij)} | Users: {len(users)} | Postcodes: {len(postcodes)}")

        time.sleep(30)


if __name__ == "__main__":
    main()
