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
    Stuurt een Telegram bericht met de pand analyse.
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

    # Telegram MarkdownV2 vereist escapen van speciale tekens
    def esc(tekst):
        if not tekst:
            return ""
        for c in ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']:
            tekst = str(tekst).replace(c, f'\\{c}')
        return tekst

    bericht = f"""{emoji} *IMMO ALERT \\- {esc(aanbeveling.replace('_', ' '))}*

📍 *{esc(pand.get('gemeente', '?'))} \\- {esc(pand.get('postcode', '?'))}*
{esc(pand.get('straat', ''))} {esc(pand.get('huisnummer', ''))}

🏠 {esc(pand.get('type', '?'))} \\| {esc(pand.get('bewoonbare_opp', 0))}m² woning \\| {esc(pand.get('perceel_opp', 0))}m² perceel
💶 *Prijs: €{esc(f"{pand.get('prijs', 0):,}")}*
🛏️ {esc(pand.get('slaapkamers', 0))} slaapkamers \\| EPC: {esc(pand.get('epc_score', '?'))}

━━━━━━━━━━━━━━━━━━━━
📊 *FINANCIEEL OVERZICHT*

💸 Aankoopkost: €{esc(str(metrics.get('totale_aankoopkost', 0)))}
📈 Bruto rendement: *{esc(metrics.get('bruto_rendement', 0))}%*
🏗️ Projectmarge: *{esc(metrics.get('project_marge', 0))}%*
🏢 Geschat {esc(metrics.get('geschat_aantal_appartementen', 0))} appartementen mogelijk

━━━━━━━━━━━━━━━━━━━━
🤖 *AI BEOORDELING*

{esc(ai_analyse.get('korte_uitleg', ''))}

💡 Beste strategie: *{esc(strategie)}*
⭐ Prioriteit: {esc(ai_analyse.get('prioriteit', 5))}/10

✅ *Kansen:*
{esc(kansen_tekst)}

⚠️ *Risico's:*
{esc(risicos_tekst)}

━━━━━━━━━━━━━━━━━━━━
🔗 {pand.get('url', '')}"""

    return _verstuur_bericht(bericht, config)


def stuur_opstart_bericht(config) -> bool:
    """Stuurt een testbericht bij opstart."""
    bericht = "🚀 *Immo Scanner gestart\\!*\n\nIk ga nu automatisch Immoweb in de gaten houden en u verwittigen bij interessante panden\\."
    return _verstuur_bericht(bericht, config)


def _verstuur_bericht(tekst: str, config) -> bool:
    """
    Interne functie om een bericht te sturen via Telegram Bot API.
    """
    url = f"{TELEGRAM_API}{config.TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": tekst,
        "parse_mode": "MarkdownV2",
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
