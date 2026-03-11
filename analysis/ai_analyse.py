"""
AI Analyse Module - Trechtersysteem
Analyseert panden in stappen van goedkoop naar duur:

Stap 1: Snelle check (goedkoop model, alleen cijfers)      ~400 tokens
Stap 2: Locatie check (+ Wikipedia/Statbel data)           ~600 tokens  
Stap 3: Foto analyse (wat ziet de AI op de foto's)         ~500 tokens
Stap 4: Volledige analyse (krachtig model, alles samen)    ~1200 tokens

Alleen panden die stap 1+2 passeren krijgen stap 3+4.
Zo besparen we tokens voor panden die het echt waard zijn.
"""

import requests
import json
import logging
import time
from analysis.locatie_info import haal_gemeente_info_op, formatteer_locatie_context
from analysis.feedback import genereer_lessen_voor_ai
from analysis.token_tracker import kan_aanroepen, registreer_gebruik, budget_status
import config2

logger = logging.getLogger(__name__)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


def _groq_call(prompt: str, model: str, max_tokens: int, api_key: str, systeem: str = None) -> tuple[str, int]:
    """
    Basis Groq API call. Geeft (antwoord_tekst, tokens_gebruikt) terug.
    Wacht automatisch als de limiet bereikt is.
    """
    geschat = len(prompt.split()) * 1.3 + max_tokens

    # Wacht als nodig
    for poging in range(5):
        ok, reden = kan_aanroepen(int(geschat), config2.TOKENS_PER_MINUUT_LIMIET, config2.TOKENS_PER_DAG_LIMIET)
        if ok:
            break
        logger.info(f"⏳ Token limiet: {reden} — wachten...")
        time.sleep(15)
    else:
        return "", 0

    berichten = []
    if systeem:
        berichten.append({"role": "system", "content": systeem})
    berichten.append({"role": "user", "content": prompt})

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "max_tokens": max_tokens, "temperature": 0.2, "messages": berichten},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            tekst = data["choices"][0]["message"]["content"].strip()
            tokens = data.get("usage", {}).get("total_tokens", int(geschat))
            registreer_gebruik(tokens)
            return tekst, tokens

        elif response.status_code == 429:
            logger.warning("Rate limit 429 — 30s wachten...")
            time.sleep(30)
            return "", 0
        else:
            logger.error(f"Groq fout: {response.status_code}")
            return "", 0

    except Exception as e:
        logger.error(f"Groq call fout: {e}")
        return "", 0


def _parse_json(tekst: str) -> dict:
    """Parset JSON uit AI antwoord, ook als er markdown omheen zit."""
    if "```" in tekst:
        tekst = tekst.split("```")[1]
        if tekst.startswith("json"):
            tekst = tekst[4:]
    tekst = tekst.strip()
    try:
        return json.loads(tekst)
    except Exception:
        return {}


# ─── STAP 1: SNELLE CHECK ────────────────────────────────────────────────────

def snelle_check(pand: dict, metrics: dict, api_key: str) -> tuple[int, str]:
    """
    Goedkope snelle check op basis van alleen de cijfers.
    Gebruikt klein model (~400 tokens).
    Geeft (score 0-100, reden) terug.
    """
    prompt = f"""Belgische vastgoedexpert. Beoordeel dit pand ALLEEN op basis van de cijfers.
Geef een score van 0-100 en of het de moeite waard is om dieper te analyseren.

Prijs: EUR {pand.get('prijs', 0):,}
Perceel: {pand.get('perceel_opp', 0)}m2 | Woning: {pand.get('bewoonbare_opp', 0)}m2
Prijs/m2 woning: EUR {metrics.get('prijs_per_m2', 0)} | Prijs/m2 perceel: EUR {metrics.get('prijs_per_m2_perceel', 0)}
Bruto rendement: {metrics.get('bruto_rendement', 0)}% | Projectmarge: {metrics.get('project_marge', 0)}%
Geschatte apps: {metrics.get('geschat_aantal_appartementen', 0)} | EPC: {pand.get('epc_score', '?')}
Bouwjaar: {pand.get('bouwjaar', '?')} | Staat: {pand.get('staat', '?')}
Gemeente: {pand.get('gemeente', '?')}

Antwoord ALLEEN in JSON: {{"score": 75, "verder_analyseren": true, "reden": "1 zin reden"}}"""

    tekst, tokens = _groq_call(prompt, config2.GROQ_MODEL_SNEL, 150, api_key)
    if not tekst:
        return 50, "check mislukt"

    data = _parse_json(tekst)
    score = data.get("score", 50)
    reden = data.get("reden", "")
    verder = data.get("verder_analyseren", score >= config2.DREMPEL_SNELLE_CHECK)

    logger.info(f"  Stap 1 snelle check: {score}/100 — {reden} ({tokens} tokens)")
    return score if verder else 0, reden


# ─── STAP 2: LOCATIE CHECK ───────────────────────────────────────────────────

def locatie_check(pand: dict, metrics: dict, snelle_score: int, api_key: str) -> tuple[int, str]:
    """
    Voegt locatiedata toe aan de beoordeling.
    Gebruikt klein model (~600 tokens).
    """
    gemeente = pand.get('gemeente', '')
    postcode = pand.get('postcode', '')
    locatie_info = haal_gemeente_info_op(gemeente, postcode)
    locatie_context = formatteer_locatie_context(locatie_info)

    prompt = f"""Belgische vastgoedexpert. Beoordeel de locatie van dit pand.

{locatie_context}

Pand: {pand.get('type', '?')} in {gemeente} ({postcode})
Prijs: EUR {pand.get('prijs', 0):,} | Perceel: {pand.get('perceel_opp', 0)}m2
Vorige score (cijfers): {snelle_score}/100

Is de locatie interessant voor projectontwikkeling?
Antwoord ALLEEN in JSON: {{"score": 70, "verder_analyseren": true, "locatie_beoordeling": "1 zin over ligging"}}"""

    tekst, tokens = _groq_call(prompt, config2.GROQ_MODEL_SNEL, 150, api_key)
    if not tekst:
        return snelle_score, "locatiecheck mislukt"

    data = _parse_json(tekst)
    score = data.get("score", snelle_score)
    beoordeling = data.get("locatie_beoordeling", "")
    verder = data.get("verder_analyseren", score >= config2.DREMPEL_LOCATIE_CHECK)

    logger.info(f"  Stap 2 locatie check: {score}/100 — {beoordeling} ({tokens} tokens)")
    return score if verder else 0, beoordeling


# ─── STAP 3: FOTO ANALYSE ────────────────────────────────────────────────────

def foto_analyse(pand: dict, api_key: str) -> str:
    """
    Analyseert de foto's van het pand.
    Gebruikt klein model (~500 tokens).
    """
    foto_urls = pand.get("alle_fotos", [])
    if not foto_urls and pand.get("foto_url"):
        foto_urls = [pand.get("foto_url")]
    if not foto_urls:
        return "Geen foto's beschikbaar."

    urls = foto_urls[:3]
    prompt = f"""Bekijk deze vastgoedfoto's en beschrijf in max 3 zinnen:
1. Staat van het pand (goed/matig/slecht)
2. Wat gerenoveerd moet worden
3. Sloopkandidaat of renovatiekandidaat?

Foto's: {', '.join(urls)}
Antwoord in het Nederlands, max 3 zinnen, zeer concreet."""

    tekst, tokens = _groq_call(prompt, config2.GROQ_MODEL_SNEL, 200, api_key)
    logger.info(f"  Stap 3 foto analyse: {tokens} tokens")
    return tekst if tekst else "Fotoanalyse niet beschikbaar."


# ─── STAP 4: VOLLEDIGE ANALYSE ───────────────────────────────────────────────

def volledige_analyse(pand: dict, metrics: dict, locatie_context: str,
                      foto_resultaat: str, api_key: str) -> dict:
    """
    Diepe volledige analyse met het krachtige model.
    Alleen voor panden die stap 1+2+3 gepasseerd zijn (~1200 tokens).
    """
    lessen = genereer_lessen_voor_ai()

    prompt = f"""Je bent een ervaren Belgische projectontwikkelaar met 20 jaar ervaring in Vlaanderen.
Je hebt al honderden projecten gedaan en bent kritisch en realistisch.

=== LOCATIE ===
{locatie_context}

=== FOTO ANALYSE ===
{foto_resultaat}

{lessen}

=== PAND ===
Type: {pand.get('type', '?')} - {pand.get('subtype', '')}
Adres: {pand.get('straat', '')} {pand.get('huisnummer', '')}, {pand.get('postcode', '')} {pand.get('gemeente', '')}
Prijs: EUR {pand.get('prijs', 0):,} | Bouwjaar: {pand.get('bouwjaar', '?')}
Woning: {pand.get('bewoonbare_opp', 0)}m2 | Perceel: {pand.get('perceel_opp', 0)}m2
Slaapkamers: {pand.get('slaapkamers', 0)} | EPC: {pand.get('epc_score', '?')} ({pand.get('epc_waarde', 0)} kWh/m2)
Staat: {pand.get('staat', '?')} | Tuin: {'ja' if pand.get('tuin') else 'nee'}

=== FINANCIEEL ===
Aankoopkost: EUR {metrics.get('totale_aankoopkost', 0):,}
Prijs/m2: EUR {metrics.get('prijs_per_m2', 0)} | Prijs/m2 perceel: EUR {metrics.get('prijs_per_m2_perceel', 0)}
Huur/maand: EUR {metrics.get('geschatte_huur_maand', 0):,} | Bruto rendement: {metrics.get('bruto_rendement', 0)}%
Netto rendement: {metrics.get('netto_rendement', 0)}% | Projectmarge: {metrics.get('project_marge', 0)}%
Apps mogelijk: {metrics.get('geschat_aantal_appartementen', 0)} ({metrics.get('app_schatting_uitleg', '')})
Projectwinst: EUR {metrics.get('project_winst', 0):,} | Renovatiekost: EUR {metrics.get('renovatiekost', 0):,}

=== BEOORDELINGSCRITERIA ===
GROEN: perceel >500m2 centrumstad, prijs/m2 <EUR1200, marge >20%, rendement >6%, sloopkandidaat
ROOD: prijs/m2 perceel >EUR1200, marge <5%, perceel <150m2, rendement <2.5%
REALISTISCH: stedenbouwkundig attest bepaalt werkelijk aantal apps, niet enkel de m2

Antwoord ALLEEN in JSON:
{{
  "aanbeveling": "STERK_AAN",
  "korte_uitleg": "Max 2 concrete zinnen hoofdreden",
  "kansen": ["kans 1", "kans 2", "kans 3"],
  "risicos": ["risico 1", "risico 2"],
  "beste_strategie": "SLOOP_HERBOUW",
  "prioriteit": 8
}}

aanbeveling: STERK_AAN / AAN / NEUTRAAL / AF / STERK_AF
beste_strategie: VERHUUR / SLOOP_HERBOUW / RENOVATIE_VERHUUR / DOORVERKOOP
prioriteit: 1-10 (10 = morgen bezichtigen!)"""

    tekst, tokens = _groq_call(
        prompt, config2.GROQ_MODEL_KRACHTIG, 500, api_key,
        systeem="Belgische vastgoedexpert. Antwoord alleen in geldig JSON."
    )
    logger.info(f"  Stap 4 volledige analyse: {tokens} tokens")

    if not tekst:
        return {"aanbeveling": "NEUTRAAL", "korte_uitleg": "Analyse mislukt", "kansen": [], "risicos": [], "beste_strategie": "ONBEKEND", "prioriteit": 5}

    resultaat = _parse_json(tekst)
    if not resultaat:
        return {"aanbeveling": "NEUTRAAL", "korte_uitleg": "JSON parse fout", "kansen": [], "risicos": [], "beste_strategie": "ONBEKEND", "prioriteit": 5}

    return resultaat


# ─── HOOFD FUNCTIE ───────────────────────────────────────────────────────────

def analyseer_pand_met_ai(pand: dict, metrics: dict, api_key: str) -> dict:
    """
    Analyseert een pand via het trechtersysteem.
    Stopt vroeg als een pand niet interessant genoeg is.
    """
    gemeente = pand.get('gemeente', '?')
    prijs = pand.get('prijs', 0)

    # Toon budget status
    status = budget_status(config2.TOKENS_PER_MINUUT_LIMIET, config2.TOKENS_PER_DAG_LIMIET)
    logger.info(f"💰 Tokens vandaag: {status['dag_gebruikt']:,}/{status['dag_over']+status['dag_gebruikt']:,} ({status['dag_pct']}%) | Minuut: {status['minuut_gebruikt']}/{config2.TOKENS_PER_MINUUT_LIMIET}")

    NIET_INTERESSANT = {"aanbeveling": "AF", "korte_uitleg": "Niet door voorfilter", "kansen": [], "risicos": [], "beste_strategie": "ONBEKEND", "prioriteit": 1}

    # ── Stap 1: Snelle check ────────────────────────────────────────────
    score1, reden1 = snelle_check(pand, metrics, api_key)
    if score1 < config2.DREMPEL_SNELLE_CHECK:
        logger.info(f"  ❌ Gestopt na stap 1: {reden1}")
        return NIET_INTERESSANT

    # ── Stap 2: Locatie check ───────────────────────────────────────────
    score2, reden2 = locatie_check(pand, metrics, score1, api_key)
    if score2 < config2.DREMPEL_LOCATIE_CHECK:
        logger.info(f"  ❌ Gestopt na stap 2: {reden2}")
        return NIET_INTERESSANT

    # ── Stap 3: Foto analyse ────────────────────────────────────────────
    foto_resultaat = foto_analyse(pand, api_key)

    # ── Stap 4: Volledige analyse ───────────────────────────────────────
    gemeente_info = haal_gemeente_info_op(pand.get('gemeente', ''), pand.get('postcode', ''))
    locatie_context = formatteer_locatie_context(gemeente_info)

    resultaat = volledige_analyse(pand, metrics, locatie_context, foto_resultaat, api_key)
    logger.info(f"  ✅ Volledig: {resultaat.get('aanbeveling')} | prio {resultaat.get('prioriteit')}/10")

    return resultaat
