"""
Telegram Notificatie Module
Stuurt berichten via Telegram Bot API (100% gratis!)
Nu met scorekaart, scenarios en rode vlaggen in de melding.
"""

import requests
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)
TELEGRAM_API = "https://api.telegram.org/bot"


def stuur_melding(pand: dict, metrics: dict, ai_analyse: dict, config,
                  scorekaart: dict = None) -> bool:
    """
    Stuurt een Telegram bericht met volledige analyse.
    Inclusief scorekaart, scenarios en GO/REVIEW beslissing.
    """
    aanbeveling = ai_analyse.get("aanbeveling", "NEUTRAAL")
    beslissing  = ai_analyse.get("beslissing", "REVIEW")

    emoji_map = {
        "STERK_AAN": "🔥🔥🔥",
        "AAN":       "✅",
        "NEUTRAAL":  "🔍",
        "AF":        "❌",
        "STERK_AF":  "❌❌",
    }
    beslissing_emoji = {"GO": "🟢 GO", "REVIEW": "🟡 REVIEW", "REJECT": "🔴 REJECT"}
    strategie_map = {
        "VERHUUR":          "🏠 Verhuur",
        "SLOOP_HERBOUW":    "🏗️ Sloop & herbouw",
        "RENOVATIE_VERHUUR":"🔨 Renovatie + verhuur",
        "DOORVERKOOP":      "💰 Doorverkoop",
    }

    emoji    = emoji_map.get(aanbeveling, "🔍")
    strategie = strategie_map.get(ai_analyse.get("beste_strategie", ""), "Onbekend")
    beslissing_tekst = beslissing_emoji.get(beslissing, "🟡 REVIEW")

    kansen_tekst  = "\n".join([f"  + {k}" for k in ai_analyse.get("kansen",  [])[:3]])
    risicos_tekst = "\n".join([f"  - {r}" for r in ai_analyse.get("risicos", [])[:2]])
    pand_id = str(pand.get("id", ""))

    # Scorekaart blok
    score_blok = ""
    if scorekaart:
        ss = scorekaart.get("subscores", {})
        totaal = scorekaart.get("totale_score", 0)
        score_blok = f"""
SCOREKAART ({totaal:.0f}/100)
  Locatie:    {ss.get('locatie',0):.0f}/100
  Juridisch:  {ss.get('juridisch',0):.0f}/100
  Financieel: {ss.get('financieel',0):.0f}/100
  Technisch:  {ss.get('technisch',0):.0f}/100
  Markt:      {ss.get('markt',0):.0f}/100
  Strategie:  {ss.get('strategie',0):.0f}/100"""

    # Scenarios blok
    scenario_blok = ""
    if scorekaart and scorekaart.get("scenarios"):
        sc = scorekaart["scenarios"]
        if "realistisch" in sc:
            r = sc["realistisch"]
            p = sc.get("pessimistisch", {})
            o = sc.get("optimistisch", {})
            if "marge_pct" in r:
                scenario_blok = f"""
SCENARIOS (sloop/herbouw)
  Pessimistisch: {p.get('marge_pct',0)}% marge
  Realistisch:   {r.get('marge_pct',0)}% marge (winst EUR {r.get('winst',0):,})
  Optimistisch:  {o.get('marge_pct',0)}% marge"""
            elif "rendement_pct" in r:
                scenario_blok = f"""
SCENARIOS (verhuur)
  Pessimistisch: {p.get('rendement_pct',0)}% rendement
  Realistisch:   {r.get('rendement_pct',0)}% rendement
  Optimistisch:  {o.get('rendement_pct',0)}% rendement"""

    # Zachte vlaggen
    vlaggen_tekst = ""
    if scorekaart and scorekaart.get("zachte_vlaggen"):
        vlaggen = scorekaart["zachte_vlaggen"]
        vlaggen_tekst = f"\nLet op: {', '.join(vlaggen)}"

    bericht = f"""{emoji} IMMO ALERT - {beslissing_tekst}

ADRES
{pand.get('gemeente', '?')} ({pand.get('postcode', '?')})
{pand.get('straat', '')} {pand.get('huisnummer', '')}

PAND
Type: {pand.get('type', '?')} | {pand.get('bewoonbare_opp', 0)}m2 woning | {pand.get('perceel_opp', 0)}m2 perceel
Prijs: EUR {pand.get('prijs', 0):,} | {pand.get('slaapkamers', 0)} slaapkamers | EPC {pand.get('epc_score', '?')}
Bouwjaar: {pand.get('bouwjaar', '?')} | Staat: {pand.get('staat', '?')}

FINANCIEEL
Aankoopkost: EUR {metrics.get('totale_aankoopkost', 0):,}
Bruto rendement: {metrics.get('bruto_rendement', 0)}% | Netto: {metrics.get('netto_rendement', 0)}%
Projectmarge: {metrics.get('project_marge', 0)}% | Geschat {metrics.get('geschat_aantal_appartementen', 0)} apps
{score_blok}
{scenario_blok}

AI BEOORDELING ({aanbeveling}) - Prio {ai_analyse.get('prioriteit', 5)}/10
{ai_analyse.get('korte_uitleg', '')}
Strategie: {strategie}

Kansen:
{kansen_tekst}

Risicos:
{risicos_tekst}
{vlaggen_tekst}

{pand.get('url', '')}

Wat vindt u van dit pand?"""

    keyboard = {
        "inline_keyboard": [[
            {"text": "👍 Interessant",      "callback_data": f"goed_{pand_id}"},
            {"text": "👎 Niet interessant", "callback_data": f"slecht_{pand_id}"},
        ]]
    }

    return _verstuur_bericht_met_knoppen(bericht, keyboard, config)


def stuur_opstart_bericht(config) -> bool:
    bericht = "Immo Scanner gestart!\n\nIk scan Immoweb automatisch en verwittig u bij interessante panden.\nScorekaart: GO (>=75) / REVIEW (>=60) / REJECT (<60)"
    return _verstuur_bericht(bericht, config)


def _verstuur_bericht_met_knoppen(tekst: str, keyboard: dict, config) -> bool:
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": tekst,
            "reply_markup": keyboard,
            "disable_web_page_preview": True,
        }, timeout=15)
        if r.status_code == 200:
            return True
        logger.error(f"Telegram fout: {r.status_code} - {r.text}")
        return False
    except Exception as e:
        logger.error(f"Telegram fout: {e}")
        return False


def _verstuur_bericht(tekst: str, config) -> bool:
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": tekst,
            "disable_web_page_preview": True,
        }, timeout=15)
        return r.status_code == 200
    except Exception as e:
        logger.error(f"Telegram fout: {e}")
        return False


def verwerk_feedback_updates(config) -> list:
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/getUpdates"
    offset_bestand = Path("telegram_offset.json")
    offset = 0
    if offset_bestand.exists():
        with open(offset_bestand) as f:
            offset = json.load(f).get("offset", 0)
    try:
        r = requests.get(url, params={"offset": offset, "timeout": 5}, timeout=10)
        if r.status_code != 200:
            return []
        resultaten = []
        for update in r.json().get("result", []):
            update_id = update.get("update_id", 0)
            offset = max(offset, update_id + 1)
            callback = update.get("callback_query")
            if callback:
                data = callback.get("data", "")
                if "_" in data:
                    ftype, pand_id = data.split("_", 1)
                    if ftype in ["goed", "slecht"]:
                        resultaten.append((pand_id, ftype))
                        antwoord = "👍 Super, ik onthoud dit!" if ftype == "goed" else "👎 Begrepen, ik leer hiervan!"
                        _beantwoord_callback(callback["id"], antwoord, config)
        with open(offset_bestand, "w") as f:
            json.dump({"offset": offset}, f)
        return resultaten
    except Exception as e:
        logger.error(f"Feedback ophalen fout: {e}")
        return []


def _beantwoord_callback(callback_id: str, tekst: str, config):
    try:
        requests.post(
            f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": tekst},
            timeout=10
        )
    except Exception:
        pass
