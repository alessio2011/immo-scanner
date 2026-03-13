"""
Gemini Flash 2.0 Analyse Module
Gratis alternatief voor Groq — geen tokenlimieten op de gratis tier.

Gratis limieten Gemini Flash 2.0:
- 1.500 aanroepen/dag
- 1.000.000 tokens/minuut
- 15 aanroepen/minuut

Key ophalen: https://aistudio.google.com (gratis Google account)
Zet in config.py: GEMINI_API_KEY = "AIza..."
"""

import requests
import json
import logging
import time
from analysis.locatie_info import haal_gemeente_info_op, formatteer_locatie_context
from analysis.feedback import genereer_lessen_voor_ai

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_MODEL   = "gemini-2.0-flash"
GEMINI_BACKUP  = "gemini-1.5-flash"

# Rate limiting gratis tier: max 15/min
_laatste_aanroep = 0.0
_MIN_INTERVAL    = 4.5   # seconden tussen aanroepen (13/min = veilig)


def _gemini_call(prompt: str, api_key: str, systeem: str = None,
                 model: str = GEMINI_MODEL, max_tokens: int = 1000) -> str:
    global _laatste_aanroep

    wacht = _MIN_INTERVAL - (time.time() - _laatste_aanroep)
    if wacht > 0:
        time.sleep(wacht)
    _laatste_aanroep = time.time()

    url = GEMINI_API_URL.format(model=model)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.15,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }
    if systeem:
        payload["system_instruction"] = {"parts": [{"text": systeem}]}

    try:
        r = requests.post(url, params={"key": api_key}, json=payload, timeout=45)

        if r.status_code == 200:
            data = r.json()
            kandidaten = data.get("candidates", [])
            if kandidaten:
                return kandidaten[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            return ""

        elif r.status_code == 429:
            logger.warning("Gemini rate limit — 65s wachten...")
            time.sleep(65)
            return ""

        elif r.status_code == 503:
            logger.warning("Gemini overbelast — 30s wachten, retry backup model")
            time.sleep(30)
            if model != GEMINI_BACKUP:
                return _gemini_call(prompt, api_key, systeem, model=GEMINI_BACKUP, max_tokens=max_tokens)
            return ""

        else:
            logger.error(f"Gemini HTTP {r.status_code}: {r.text[:200]}")
            return ""

    except requests.Timeout:
        logger.warning("Gemini timeout")
        return ""
    except Exception as e:
        logger.error(f"Gemini fout: {e}")
        return ""


def _parse_json(tekst: str) -> dict:
    if not tekst:
        return {}
    if "```" in tekst:
        tekst = tekst.split("```")[1]
        if tekst.startswith("json"):
            tekst = tekst[4:]
    try:
        return json.loads(tekst.strip())
    except Exception:
        try:
            start = tekst.index("{")
            einde = tekst.rindex("}") + 1
            return json.loads(tekst[start:einde])
        except Exception:
            logger.warning(f"Gemini JSON parse fout: {tekst[:100]}")
            return {}


def analyseer_pand_met_gemini(pand: dict, metrics: dict, api_key: str) -> dict:
    """
    Volledige pand analyse in 1 Gemini call.
    Geen trechter nodig — Gemini is gratis en sterk genoeg voor directe volledige analyse.
    """
    if not api_key:
        logger.error("GEMINI_API_KEY niet ingesteld")
        return _fallback("Gemini key ontbreekt")

    gemeente = pand.get("gemeente", "?")
    postcode = pand.get("postcode", "?")

    try:
        gemeente_info   = haal_gemeente_info_op(gemeente, postcode)
        locatie_context = formatteer_locatie_context(gemeente_info)
    except Exception:
        locatie_context = f"Gemeente: {gemeente} ({postcode})"

    try:
        lessen = genereer_lessen_voor_ai()
    except Exception:
        lessen = ""

    foto_urls = pand.get("alle_fotos", [])
    if not foto_urls and pand.get("foto_url"):
        foto_urls = [pand.get("foto_url")]
    foto_tekst = f"Foto URLs (beoordeel staat): {', '.join(foto_urls[:3])}" if foto_urls else "Geen foto's beschikbaar."

    systeem = (
        "Je bent een ervaren Belgische projectontwikkelaar met 20 jaar ervaring in Vlaanderen. "
        "Je hebt honderden projecten gedaan: sloop/herbouw, renovatie, opsplitsing, verhuur. "
        "Je bent kritisch en realistisch. Je antwoordt ALTIJD in geldig JSON zonder extra tekst.\n\n"

        "BELGISCHE CONTEXT:\n"
        "- Registratierechten: 3% (klein beschrijf) of 12% + notaris 1-2%\n"
        "- BTW nieuwbouw constructie: 21%\n"
        "- Stedenbouwkundig attest verplicht voor opsplitsing/optoppen\n"
        "- RUP bepaalt wat mag — gewestplan is een startpunt, niet het eindwoord\n"
        "- Typische bouwkost Limburg: €1.800-2.200/m² excl. architect, BTW, studie\n"
        "- Limburg huurmarkt: €7-10/m²/maand appartementen\n"
        "- Parkeernorm: vaak 1 parkeerplaats per appartement verplicht\n\n"

        "GROENE SIGNALEN:\n"
        "- Perceel >500m² woongebied centrumstad\n"
        "- Prijs/m² perceel <€600 centrumstad, <€300 buiten\n"
        "- Projectmarge >20%\n"
        "- Bruto rendement >6%\n"
        "- EPC F/G of sloopkandidaat\n"
        "- Hoekpand of brede voorgevel\n\n"

        "RODE VLAGGEN:\n"
        "- Prijs/m² perceel >€1.200\n"
        "- Projectmarge <5%\n"
        "- Perceel <150m²\n"
        "- Rendement <2.5%\n"
        "- Agrarisch/industrieel gebied\n"
        "- Appartement zonder akkoord mede-eigenaars"
    )

    prompt = f"""Analyseer dit Belgisch vastgoedpand voor projectontwikkelingspotentieel.

=== LOCATIE ===
{locatie_context}

=== PAND ===
Type: {pand.get('type','?')} — {pand.get('subtype','')}
Adres: {pand.get('straat','')} {pand.get('huisnummer','')}, {postcode} {gemeente}
Prijs: €{pand.get('prijs',0):,} | Bouwjaar: {pand.get('bouwjaar','onbekend')}
Bewoonbaar: {pand.get('bewoonbare_opp',0)}m² | Perceel: {pand.get('perceel_opp',0)}m²
Slaapkamers: {pand.get('slaapkamers',0)} | EPC: {pand.get('epc_score','?')} ({pand.get('epc_waarde',0)} kWh/m²)
Staat: {pand.get('staat','onbekend')} | Tuin: {'ja' if pand.get('tuin') else 'nee'}
{foto_tekst}

=== FINANCIEEL ===
Totale aankoopkost: €{metrics.get('totale_aankoopkost',0):,}
Prijs/m² woning: €{metrics.get('prijs_per_m2',0):,} | Prijs/m² perceel: €{metrics.get('prijs_per_m2_perceel',0):,}
Bruto rendement: {metrics.get('bruto_rendement',0)}% | Netto rendement: {metrics.get('netto_rendement',0)}%
Projectmarge: {metrics.get('project_marge',0)}% | Geschat apps: {metrics.get('geschat_aantal_appartementen',0)}
Huur/maand: €{metrics.get('geschatte_huur_maand',0):,} | Projectwinst: €{metrics.get('project_winst',0):,}
Renovatiekost: €{metrics.get('renovatiekost',0):,}

{lessen}

Antwoord STRIKT in dit JSON (geen andere tekst):
{{
  "aanbeveling": "STERK_AAN",
  "korte_uitleg": "Max 2 concrete zinnen met specifieke cijfers over hoofdreden.",
  "kansen": ["Kans 1 met cijfers", "Kans 2", "Kans 3"],
  "risicos": ["Risico 1 met reden", "Risico 2"],
  "beste_strategie": "SLOOP_HERBOUW",
  "prioriteit": 8,
  "foto_beoordeling": "Zichtbare staat pand of geen fotos"
}}

aanbeveling: STERK_AAN / AAN / NEUTRAAL / AF / STERK_AF
beste_strategie: VERHUUR / SLOOP_HERBOUW / RENOVATIE_VERHUUR / DOORVERKOOP
prioriteit: 1-10 (10 = morgen bezichtigen)"""

    logger.info(f"  🤖 Gemini: {gemeente} ({postcode})")
    tekst = _gemini_call(prompt, api_key, systeem=systeem, max_tokens=800)

    if not tekst:
        return _fallback("Geen antwoord van Gemini")

    resultaat = _parse_json(tekst)
    if not resultaat:
        return _fallback("JSON parse fout")

    resultaat.setdefault("aanbeveling",    "NEUTRAAL")
    resultaat.setdefault("korte_uitleg",   "Geen uitleg")
    resultaat.setdefault("kansen",         [])
    resultaat.setdefault("risicos",        [])
    resultaat.setdefault("beste_strategie","ONBEKEND")
    resultaat.setdefault("prioriteit",     5)

    logger.info(f"  ✅ Gemini: {resultaat['aanbeveling']} | prio {resultaat['prioriteit']}/10")
    return resultaat


def _fallback(reden: str) -> dict:
    return {
        "aanbeveling":    "NEUTRAAL",
        "korte_uitleg":   f"Gemini analyse mislukt: {reden}",
        "kansen":         [],
        "risicos":        ["AI analyse niet beschikbaar — manueel controleren"],
        "beste_strategie":"ONBEKEND",
        "prioriteit":     3,
        "foto_beoordeling": "niet beschikbaar",
    }


def gemini_juridisch_call(prompt: str, api_key: str) -> str:
    """Voor juridisch.py — aparte call met juridische system prompt."""
    systeem = (
        "Je bent een Belgische stedenbouwkundige expert gespecialiseerd in Vlaanderen. "
        "Je kent RUP-regels, gewestplanbestemmingen en projectontwikkelingsprocedures. "
        "Antwoord ALTIJD in geldig JSON zonder extra tekst."
    )
    return _gemini_call(prompt, api_key, systeem=systeem, max_tokens=700)
