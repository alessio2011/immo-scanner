"""
AI Analyse Module
Gebruikt Groq (gratis) om een pand te beoordelen als projectontwikkelaar
Gratis account: groqcloud.com → 1000 requests/dag
"""

import requests
import json
import logging

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Krachtig gratis model van Groq


def analyseer_pand_met_ai(pand: dict, metrics: dict, api_key: str) -> dict:
    """
    Stuurt pand info naar Groq (Llama) voor een expertbeoordeling.
    Geeft een dict terug met: aanbeveling, uitleg, risicos, kansen
    """

    prompt = f"""Je bent een ervaren Belgische vastgoedexpert en projectontwikkelaar met 20 jaar ervaring.
Beoordeel dit pand vanuit projectontwikkelingsperspectief (sloop/herbouw of renovatie voor verhuur).

=== PAND INFORMATIE ===
Type: {pand.get('type', 'onbekend')} - {pand.get('subtype', '')}
Locatie: {pand.get('straat', '')} {pand.get('huisnummer', '')}, {pand.get('postcode', '')} {pand.get('gemeente', '')}
Prijs: €{pand.get('prijs', 0):,}
Bewoonbare oppervlakte: {pand.get('bewoonbare_opp', 0)} m²
Perceeloppervlakte: {pand.get('perceel_opp', 0)} m²
Slaapkamers: {pand.get('slaapkamers', 0)}
Bouwjaar: {pand.get('bouwjaar', 'onbekend')}
EPC score: {pand.get('epc_score', 'onbekend')} ({pand.get('epc_waarde', 0)} kWh/m²jaar)
Staat: {pand.get('staat', 'onbekend')}
Tuin: {'Ja' if pand.get('tuin') else 'Nee'}

=== FINANCIËLE BEREKENINGEN ===
Totale aankoopkost (incl. notaris): €{metrics.get('totale_aankoopkost', 0):,}
Prijs per m² woning: €{metrics.get('prijs_per_m2', 0):,}
Prijs per m² perceel: €{metrics.get('prijs_per_m2_perceel', 0):,}

VERHUURSCENARIO:
- Geschatte huur/maand: €{metrics.get('geschatte_huur_maand', 0):,}
- Bruto rendement: {metrics.get('bruto_rendement', 0)}%
- Netto rendement: {metrics.get('netto_rendement', 0)}%

PROJECTONTWIKKELING (sloop/herbouw):
- Geschat aantal appartementen: {metrics.get('geschat_aantal_appartementen', 0)}
- Geschatte verkoopopbrengst: €{metrics.get('geschatte_verkoopopbrengst', 0):,}
- Totale projectkosten: €{metrics.get('totale_projectkosten', 0):,}
- Geschatte winst: €{metrics.get('project_winst', 0):,}
- Projectmarge: {metrics.get('project_marge', 0)}%

RENOVATIESCENARIO:
- Renovatie nodig: {'Ja' if metrics.get('renovatie_nodig') else 'Nee'}
- Geschatte renovatiekost: €{metrics.get('renovatiekost', 0):,}
- Totaal na renovatie: €{metrics.get('totaal_na_renovatie', 0):,}

=== GEVRAAGDE ANALYSE ===
Antwoord ALLEEN met dit JSON formaat, geen andere tekst, geen uitleg erbuiten:
{{
  "aanbeveling": "STERK_AAN",
  "korte_uitleg": "Max 2 zinnen waarom wel/niet interessant",
  "kansen": ["kans 1", "kans 2", "kans 3"],
  "risicos": ["risico 1", "risico 2"],
  "beste_strategie": "VERHUUR",
  "prioriteit": 7
}}

Mogelijke waarden:
- aanbeveling: STERK_AAN / AAN / NEUTRAAL / AF / STERK_AF
- beste_strategie: VERHUUR / SLOOP_HERBOUW / RENOVATIE_VERHUUR / DOORVERKOOP
- prioriteit: getal van 1 tot 10"""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "max_tokens": 1000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "system",
                        "content": "Je bent een Belgische vastgoedexpert. Antwoord altijd en alleen in geldig JSON formaat, zonder extra tekst."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            tekst = data["choices"][0]["message"]["content"].strip()

            # JSON parsen - verwijder eventuele markdown backticks
            if "```" in tekst:
                tekst = tekst.split("```")[1]
                if tekst.startswith("json"):
                    tekst = tekst[4:]
            tekst = tekst.strip()

            return json.loads(tekst)
        else:
            logger.error(f"Groq API fout: {response.status_code} - {response.text}")
            return {"aanbeveling": "NEUTRAAL", "korte_uitleg": "AI analyse mislukt", "kansen": [], "risicos": [], "beste_strategie": "ONBEKEND", "prioriteit": 5}

    except Exception as e:
        logger.error(f"Fout bij AI analyse: {e}")
        return {"aanbeveling": "NEUTRAAL", "korte_uitleg": f"Fout: {e}", "kansen": [], "risicos": [], "beste_strategie": "ONBEKEND", "prioriteit": 5}
