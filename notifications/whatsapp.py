"""
WhatsApp Notificatie Module
Stuurt berichten via Meta WhatsApp Business API
"""

import requests
import logging

logger = logging.getLogger(__name__)


def stuur_whatsapp_melding(pand: dict, metrics: dict, ai_analyse: dict, config) -> bool:
    """
    Stuurt een WhatsApp bericht met de pand analyse.
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

    bericht = f"""{emoji} *IMMO ALERT - {aanbeveling.replace('_', ' ')}*

📍 *{pand.get('gemeente', '?')} - {pand.get('postcode', '?')}*
{pand.get('straat', '')} {pand.get('huisnummer', '')}

🏠 *{pand.get('type', '?')}* | {pand.get('bewoonbare_opp', 0)}m² woning | {pand.get('perceel_opp', 0)}m² perceel
💶 *Prijs: €{pand.get('prijs', 0):,}*
🛏️ {pand.get('slaapkamers', 0)} slaapkamers | EPC: {pand.get('epc_score', '?')}

━━━━━━━━━━━━━━━━━━━━
📊 *FINANCIEEL OVERZICHT*

💸 Totale aankoopkost: €{metrics.get('totale_aankoopkost', 0):,}
📈 Bruto rendement: *{metrics.get('bruto_rendement', 0)}%*
🏗️ Projectmarge: *{metrics.get('project_marge', 0)}%*
🏢 Geschat {metrics.get('geschat_aantal_appartementen', 0)} appartementen mogelijk

━━━━━━━━━━━━━━━━━━━━
🤖 *AI BEOORDELING*

{ai_analyse.get('korte_uitleg', '')}

💡 Beste strategie: *{strategie}*
⭐ Prioriteit: {ai_analyse.get('prioriteit', 5)}/10

✅ *Kansen:*
{kansen_tekst}

⚠️ *Risico's:*
{risicos_tekst}

━━━━━━━━━━━━━━━━━━━━
🔗 {pand.get('url', '')}"""

    return _verstuur_bericht(bericht, config)


def stuur_opstart_bericht(config) -> bool:
    """Stuurt een testbericht bij opstart."""
    bericht = "🚀 *Immo Scanner gestart!*\n\nIk ga nu automatisch Immoweb in de gaten houden en je verwittigen bij interessante panden."
    return _verstuur_bericht(bericht, config)


def _verstuur_bericht(tekst: str, config) -> bool:
    """
    Interne functie om een bericht te sturen via WhatsApp Business API.
    """
    url = f"https://graph.facebook.com/v18.0/{config.WHATSAPP_PHONE_ID}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": config.WHATSAPP_TO_NUMBER,
        "type": "text",
        "text": {
            "preview_url": False,
            "body": tekst
        }
    }

    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            logger.info("WhatsApp bericht succesvol verstuurd")
            return True
        else:
            logger.error(f"WhatsApp fout: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Fout bij WhatsApp bericht: {e}")
        return False
