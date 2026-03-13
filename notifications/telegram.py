"""
Telegram notificaties — ALLEEN voor de admin.
Gewone users krijgen geen Telegram meldingen — zij zien alles via de website.

Admin krijgt:
- 🔥 Elk GO pand (compacte melding)
- ⚠️ REVIEW panden (korte melding)
- 🚨 Kritieke fouten
- 📊 Dagrapport (automatisch om 18u)
- 🟢 Opstart bevestiging

Config in config.py:
  TELEGRAM_BOT_TOKEN = "..."
  TELEGRAM_CHAT_ID   = "-123..."   ← jouw persoonlijke chat ID
"""

import requests
import json
import logging
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
DAGRAPPORT_BESTAND = Path("dagrapport_status.json")


# ─── BASIS HELPER ────────────────────────────────────────────────────────────

def _stuur(bot_token: str, chat_id: str, tekst: str, stil: bool = False) -> bool:
    """Stuurt een bericht naar de admin chat."""
    if not bot_token or not chat_id:
        return False
    try:
        r = requests.post(
            TELEGRAM_API.format(token=bot_token),
            json={
                "chat_id":    chat_id,
                "text":       tekst,
                "parse_mode": "HTML",
                "disable_notification": stil,
                "disable_web_page_preview": True,
            },
            timeout=10
        )
        if r.status_code != 200:
            logger.warning(f"Telegram HTTP {r.status_code}: {r.text[:100]}")
            return False
        return True
    except Exception as e:
        logger.warning(f"Telegram fout: {e}")
        return False


def _fmt_euro(bedrag) -> str:
    try:
        return f"€ {int(bedrag):,}".replace(",", ".")
    except Exception:
        return f"€ {bedrag}"


# ─── ADMIN NOTIFICATIES ───────────────────────────────────────────────────────

def stuur_opstart_bericht(bot_token: str, chat_id: str):
    """Bevestiging dat de scanner gestart is."""
    nu = datetime.now().strftime("%d/%m/%Y %H:%M")
    tekst = (
        f"🟢 <b>Immo Scanner gestart</b>\n"
        f"<code>{nu}</code>\n\n"
        f"Scanner draait. GO panden verschijnen hier automatisch."
    )
    _stuur(bot_token, chat_id, tekst, stil=True)


def stuur_go_melding(pand: dict, metrics: dict, ai: dict, bot_token: str, chat_id: str, scorekaart: dict = None):
    """
    Compacte GO melding naar admin.
    Bevat: locatie, prijs, score, strategie, top 2 kansen, Immoweb link.
    """
    gemeente  = pand.get("gemeente", "?")
    straat    = pand.get("straat", "")
    huisnr    = pand.get("huisnummer", "")
    postcode  = pand.get("postcode", "?")
    prijs     = _fmt_euro(pand.get("prijs", 0))
    perceel   = pand.get("perceel_opp", 0)
    score     = ai.get("totale_score", 0)
    strategie_map = {
        "SLOOP_HERBOUW": "Sloop/herbouw",
        "RENOVATIE_VERHUUR": "Renovatie + verhuur",
        "VERHUUR": "Verhuur",
        "DOORVERKOOP": "Doorverkoop",
    }
    strategie = strategie_map.get(ai.get("beste_strategie", ""), ai.get("beste_strategie", "?"))
    marge     = metrics.get("project_marge", 0)
    rend      = metrics.get("bruto_rendement", 0)
    uitleg    = ai.get("korte_uitleg", "")
    kansen    = ai.get("kansen", [])[:2]
    url       = pand.get("url", "")

    # Juridisch samenvatting
    jur_tekst = ""
    jur = ai.get("juridisch")
    if jur and jur.get("ai_beoordeling"):
        jb = jur["ai_beoordeling"]
        jur_tekst = (
            f"\n⚖️ <b>Juridisch:</b> {jb.get('bestemming_label','?')} · "
            f"risico: {jb.get('juridisch_risico','?')}"
        )

    kansen_tekst = ""
    if kansen:
        kansen_tekst = "\n" + "\n".join(f"  + {k}" for k in kansen)

    tekst = (
        f"🔥 <b>GO — {gemeente}</b> ({postcode})\n"
        f"📍 {straat} {huisnr}\n\n"
        f"💶 <b>{prijs}</b>  ·  {perceel}m² perceel\n"
        f"📈 Marge: <b>{marge}%</b>  ·  Rend: {rend}%\n"
        f"🏗️ Strategie: {strategie}\n"
        f"⭐ Score: <b>{score}/100</b>\n\n"
        f"<i>{uitleg}</i>"
        f"{kansen_tekst}"
        f"{jur_tekst}"
    )
    if url:
        tekst += f"\n\n🔗 <a href=\"{url}\">Immoweb →</a>"

    _stuur(bot_token, chat_id, tekst)


def stuur_review_melding(pand: dict, metrics: dict, ai: dict, bot_token: str, chat_id: str):
    """
    Korte REVIEW melding — stil (geen geluid).
    """
    gemeente = pand.get("gemeente", "?")
    prijs    = _fmt_euro(pand.get("prijs", 0))
    score    = ai.get("totale_score", 0)
    marge    = metrics.get("project_marge", 0)
    url      = pand.get("url", "")

    tekst = (
        f"👀 <b>REVIEW — {gemeente}</b>\n"
        f"{prijs}  ·  score {score}/100  ·  marge {marge}%\n"
        f"<i>{ai.get('korte_uitleg','')}</i>"
    )
    if url:
        tekst += f"\n🔗 <a href=\"{url}\">Immoweb →</a>"

    _stuur(bot_token, chat_id, tekst, stil=True)


def stuur_fout_melding(fout: str, bot_token: str, chat_id: str):
    """Kritieke fout — voor als de scanner crasht of vastloopt."""
    tekst = (
        f"🚨 <b>Scanner fout</b>\n"
        f"<code>{fout[:300]}</code>\n\n"
        f"<i>{datetime.now().strftime('%H:%M')}</i>"
    )
    _stuur(bot_token, chat_id, tekst)


def stuur_dagrapport(stats: dict, bot_token: str, chat_id: str):
    """
    Dagelijks rapport om 18u.
    stats = {go, review, reject, gescand, users, postcodes, wachtrij}
    """
    datum = datetime.now().strftime("%d/%m/%Y")
    tekst = (
        f"📊 <b>Dagrapport {datum}</b>\n\n"
        f"🟢 GO:      <b>{stats.get('go', 0)}</b>\n"
        f"🟡 REVIEW:  <b>{stats.get('review', 0)}</b>\n"
        f"🔴 REJECT:  {stats.get('reject', 0)}\n"
        f"🔍 Gescand: {stats.get('gescand', 0)}\n\n"
        f"👥 Actieve users: {stats.get('users', 0)}\n"
        f"📮 Unieke postcodes: {stats.get('postcodes', 0)}\n"
        f"⏳ Wachtrij: {stats.get('wachtrij', 0)}"
    )
    _stuur(bot_token, chat_id, tekst, stil=True)


# ─── DAGRAPPORT TIMING ────────────────────────────────────────────────────────

def check_dagrapport(stats: dict, bot_token: str, chat_id: str):
    """
    Checkt of het dagrapport al gestuurd is vandaag.
    Stuurt het als het tussen 18:00 en 18:05 is en nog niet gestuurd.
    """
    nu = datetime.now()
    if nu.hour != 18 or nu.minute > 5:
        return

    vandaag = nu.date().isoformat()
    status = {}
    if DAGRAPPORT_BESTAND.exists():
        try:
            with open(DAGRAPPORT_BESTAND) as f:
                status = json.load(f)
        except Exception:
            pass

    if status.get("datum") == vandaag:
        return  # Al gestuurd vandaag

    stuur_dagrapport(stats, bot_token, chat_id)
    with open(DAGRAPPORT_BESTAND, "w") as f:
        json.dump({"datum": vandaag, "gestuurd": nu.isoformat()}, f)
    logger.info("📊 Dagrapport gestuurd")


# ─── FEEDBACK VERWERKEN (Telegram inline knoppen) ────────────────────────────

def verwerk_feedback_updates_multi(bot_token: str) -> list:
    """
    Verwerkt Telegram callback queries voor feedback knoppen.
    Geeft lijst van (pand_id, feedback_type) terug.
    """
    if not bot_token:
        return []

    resultaten = []
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getUpdates",
            params={"timeout": 0, "limit": 20, "allowed_updates": ["callback_query"]},
            timeout=8
        )
        if r.status_code != 200:
            return []

        data = r.json()
        updates = data.get("result", [])
        if not updates:
            return []

        laatste_id = updates[-1].get("update_id", 0)

        for update in updates:
            cb = update.get("callback_query", {})
            if not cb:
                continue
            cb_data = cb.get("data", "")
            if cb_data.startswith("feedback_"):
                delen = cb_data.split("_")
                if len(delen) >= 3:
                    feedback_type = delen[1]  # goed / slecht
                    pand_id       = "_".join(delen[2:])
                    resultaten.append((pand_id, feedback_type))

                    # Bevestig de callback
                    try:
                        requests.post(
                            f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
                            json={"callback_query_id": cb["id"], "text": "✅ Feedback opgeslagen"},
                            timeout=5
                        )
                    except Exception:
                        pass

        # Update offset zodat we dezelfde updates niet opnieuw verwerken
        if laatste_id:
            requests.get(
                f"https://api.telegram.org/bot{bot_token}/getUpdates",
                params={"offset": laatste_id + 1, "limit": 1},
                timeout=5
            )

    except Exception as e:
        logger.debug(f"Feedback updates fout: {e}")

    return resultaten
