"""
Telegram Notificatie Module
Stuurt berichten via Telegram Bot API (100% gratis!)
"""

import requests
import logging

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot"


def stuur_melding(pand: dict, metrics: dict, ai_analyse: dict, config) -> bool:
    """
    Stuurt een Telegram bericht met de pand analyse + feedbackknoppen.
    """

    aanbeveling = ai_analyse.get("aanbeveling", "NEUTRAAL")
    emoji_map = {
        "STERK_AAN": "🔥🔥🔥",
        "AAN": "✅",
        "NEUTRAAL": "🔍",
        "AF": "❌",
        "STERK_AF": "❌❌",
    }
    strategie_map = {
        "VERHUUR": "🏠 Verhuur",
        "SLOOP_HERBOUW": "🏗️ Sloop & herbouw",
        "RENOVATIE_VERHUUR": "🔨 Renovatie + verhuur",
        "DOORVERKOOP": "💰 Doorverkoop",
    }

    emoji = emoji_map.get(aanbeveling, "🔍")
    strategie = strategie_map.get(ai_analyse.get("beste_strategie", ""), "Onbekend")

    kansen_tekst = "\n".join([f"  • {k}" for k in ai_analyse.get("kansen", [])[:3]])
    risicos_tekst = "\n".join([f"  • {r}" for r in ai_analyse.get("risicos", [])[:2]])

    pand_id = str(pand.get("id", ""))

    bericht = f"""{emoji} IMMO ALERT - {aanbeveling.replace('_', ' ')}

📍 {pand.get('gemeente', '?')} - {pand.get('postcode', '?')}
{pand.get('straat', '')} {pand.get('huisnummer', '')}

🏠 {pand.get('type', '?')} | {pand.get('bewoonbare_opp', 0)}m2 woning | {pand.get('perceel_opp', 0)}m2 perceel
💶 Prijs: EUR {pand.get('prijs', 0):,}
🛏 {pand.get('slaapkamers', 0)} slaapkamers | EPC: {pand.get('epc_score', '?')}

📊 FINANCIEEL OVERZICHT

Aankoopkost: EUR {metrics.get('totale_aankoopkost', 0):,}
Bruto rendement: {metrics.get('bruto_rendement', 0)}%
Projectmarge: {metrics.get('project_marge', 0)}%
Geschat {metrics.get('geschat_aantal_appartementen', 0)} appartementen mogelijk

🤖 AI BEOORDELING

{ai_analyse.get('korte_uitleg', '')}

Beste strategie: {strategie}
Prioriteit: {ai_analyse.get('prioriteit', 5)}/10

Kansen:
{kansen_tekst}

Risicos:
{risicos_tekst}

🔗 {pand.get('url', '')}

Wat vindt u van deze suggestie?"""

    # Inline knoppen voor feedback
    keyboard = {
        "inline_keyboard": [[
            {"text": "👍 Interessant", "callback_data": f"goed_{pand_id}"},
            {"text": "👎 Niet interessant", "callback_data": f"slecht_{pand_id}"},
        ]]
    }

    return _verstuur_bericht_met_knoppen(bericht, keyboard, config)


def stuur_opstart_bericht(config) -> bool:
    """Stuurt een testbericht bij opstart."""
    bericht = "🚀 Immo Scanner gestart!\n\nIk ga nu automatisch Immoweb in de gaten houden en u verwittigen bij interessante panden."
    return _verstuur_bericht(bericht, config)


def _verstuur_bericht_met_knoppen(tekst: str, keyboard: dict, config) -> bool:
    """Stuurt een bericht met inline knoppen."""
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": tekst,
        "reply_markup": keyboard,
        "disable_web_page_preview": False,
    }
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            logger.info("Telegram bericht met knoppen verstuurd")
            return True
        else:
            logger.error(f"Telegram fout: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Fout bij Telegram bericht: {e}")
        return False


def verwerk_feedback_updates(config) -> list:
    """
    Haalt nieuwe feedback op van Telegram (knopklikken).
    Geeft lijst van (pand_id, feedback) terug.
    """
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/getUpdates"

    # Laad laatste verwerkte update ID
    from pathlib import Path
    import json
    offset_bestand = Path("telegram_offset.json")
    offset = 0
    if offset_bestand.exists():
        with open(offset_bestand) as f:
            offset = json.load(f).get("offset", 0)

    try:
        response = requests.get(url, params={"offset": offset, "timeout": 5}, timeout=10)
        if response.status_code != 200:
            return []

        data = response.json()
        resultaten = []

        for update in data.get("result", []):
            update_id = update.get("update_id", 0)
            offset = max(offset, update_id + 1)

            # Verwerk knopklik
            callback = update.get("callback_query")
            if callback:
                callback_data = callback.get("data", "")
                if "_" in callback_data:
                    parts = callback_data.split("_", 1)
                    feedback_type = parts[0]   # "goed" of "slecht"
                    pand_id = parts[1]

                    if feedback_type in ["goed", "slecht"]:
                        resultaten.append((pand_id, feedback_type))

                        # Stuur bevestiging terug
                        antwoord = "👍 Super, ik onthoud dit!" if feedback_type == "goed" else "👎 Begrepen, ik leer hiervan!"
                        _beantwoord_callback(callback["id"], antwoord, config)

        # Sla nieuwe offset op
        with open(offset_bestand, "w") as f:
            json.dump({"offset": offset}, f)

        return resultaten

    except Exception as e:
        logger.error(f"Fout bij ophalen feedback: {e}")
        return []


def _beantwoord_callback(callback_id: str, tekst: str, config):
    """Beantwoordt een knopklik met een popup."""
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    try:
        requests.post(url, json={"callback_query_id": callback_id, "text": tekst}, timeout=10)
    except Exception:
        pass


def _verstuur_bericht(tekst: str, config) -> bool:
    """
    Interne functie om een bericht te sturen via Telegram Bot API.
    """
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": tekst,
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=15)

        if response.status_code == 200:
            logger.info("Telegram bericht succesvol verstuurd")
            return True
        else:
            logger.error(f"Telegram fout: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Fout bij Telegram bericht: {e}")
        return False
