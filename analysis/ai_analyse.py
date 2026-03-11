"""
AI Analyse Module
Gebruikt Groq (gratis) om een pand te beoordelen als projectontwikkelaar
Haalt ook actuele locatiedata op via Wikipedia en Statbel
Gratis account: groqcloud.com → 1000 requests/dag
"""

import requests
import json
import logging
from analysis.locatie_info import haal_gemeente_info_op, formatteer_locatie_context
from analysis.feedback import genereer_lessen_voor_ai

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Krachtig gratis model van Groq


def analyseer_pand_met_ai(pand: dict, metrics: dict, api_key: str) -> dict:
    """
    Stuurt pand info naar Groq (Llama) voor een expertbeoordeling.
    Geeft een dict terug met: aanbeveling, uitleg, risicos, kansen
    """

    # Haal lessen op uit eerdere feedback
    lessen = genereer_lessen_voor_ai()

    # Haal actuele locatiedata op
    gemeente = pand.get('gemeente', '')
    postcode = pand.get('postcode', '')
    logger.info(f"Locatiedata ophalen voor {gemeente}...")
    locatie_info = haal_gemeente_info_op(gemeente, postcode)
    locatie_context = formatteer_locatie_context(locatie_info)

    prompt = f"""Je bent een ervaren Belgische projectontwikkelaar en vastgoedexpert met 20 jaar ervaring in Vlaanderen.
Je hebt honderden projecten gedaan: sloop/herbouw, renovatie voor verhuur, en doorverkoop.
Je bent kritisch, realistisch en denkt altijd aan de werkelijke winstgevendheid.

=== ACTUELE LOCATIEDATA (opgehaald uit Wikipedia en Statbel) ===
{locatie_context}

{lessen}

=== PAND INFORMATIE ===
Type: {pand.get('type', 'onbekend')} - {pand.get('subtype', '')}
Locatie: {pand.get('straat', '')} {pand.get('huisnummer', '')}, {pand.get('postcode', '')} {pand.get('gemeente', '')}
Prijs: EUR {pand.get('prijs', 0):,}
Bewoonbare oppervlakte: {pand.get('bewoonbare_opp', 0)} m2
Perceeloppervlakte: {pand.get('perceel_opp', 0)} m2
Slaapkamers: {pand.get('slaapkamers', 0)}
Bouwjaar: {pand.get('bouwjaar', 'onbekend')}
EPC score: {pand.get('epc_score', 'onbekend')} ({pand.get('epc_waarde', 0)} kWh/m2/jaar)
Staat: {pand.get('staat', 'onbekend')}
Tuin/tuin aanwezig: {'Ja' if pand.get('tuin') else 'Nee'}

=== FINANCIËLE BEREKENINGEN ===
Totale aankoopkost (incl. 12% notaris+registratie): EUR {metrics.get('totale_aankoopkost', 0):,}
Prijs per m2 woning: EUR {metrics.get('prijs_per_m2', 0):,}
Prijs per m2 perceel: EUR {metrics.get('prijs_per_m2_perceel', 0):,}

VERHUURSCENARIO:
- Geschatte huur/maand: EUR {metrics.get('geschatte_huur_maand', 0):,}
- Bruto rendement: {metrics.get('bruto_rendement', 0)}%
- Netto rendement (na kosten): {metrics.get('netto_rendement', 0)}%

PROJECTONTWIKKELING (sloop/herbouw):
- Geschat aantal appartementen: {metrics.get('geschat_aantal_appartementen', 0)}
- Geschatte verkoopopbrengst: EUR {metrics.get('geschatte_verkoopopbrengst', 0):,}
- Totale projectkosten: EUR {metrics.get('totale_projectkosten', 0):,}
- Geschatte winst: EUR {metrics.get('project_winst', 0):,}
- Projectmarge: {metrics.get('project_marge', 0)}%

RENOVATIESCENARIO:
- Renovatie nodig: {'Ja' if metrics.get('renovatie_nodig') else 'Nee'}
- Geschatte renovatiekost: EUR {metrics.get('renovatiekost', 0):,}
- Totaal na renovatie: EUR {metrics.get('totaal_na_renovatie', 0):,}

=== JOUW BEOORDELINGSKADER ALS EXPERT ===

CRITERIA VOOR EEN INTERESSANT ONTWIKKELINGSPAND:
1. PERCEEL: Minimum 300m2 perceel voor sloop/herbouw. Hoe groter, hoe meer appartementen mogelijk.
2. PRIJS PER M2 PERCEEL: Onder EUR 400/m2 is uitstekend. EUR 400-700 is goed. Boven EUR 1000/m2 wordt moeilijk rendabel.
3. LOCATIE: Centrumsteden (Mechelen, Leuven, Gent, Antwerpen, Brussel-rand) zijn TOP. Kleine dorpen zijn risicovol.
4. PROJECTMARGE: Minimum 15% marge nodig om risico te dekken. Onder 10% is onaantrekkelijk.
5. BOUWJAAR + EPC: Panden voor 1970 met EPC F of G zijn sloopkandidaten. Renovatiekost is enorm.
6. STAAT: "To renovate" of "to be done up" = lagere prijs maar hoge renovatiekost. Afwegen.
7. HUURRENDEMENT: In Belgie is 4-6% bruto goed. Boven 6% is uitstekend. Onder 3% is slecht.
8. PERCEELVORM: Hoekpercelen of brede percelen zijn beter voor nieuwbouw dan smalle strookpercelen.
9. BESTEMMING: Check of de gemeente woonuitbreiding toelaat. Industriezones of agrarisch = probleem.
10. NETTO RENDEMENT: Realistische netto rendement in Belgie is 2.5-3.5%. Boven 4% netto is zeer goed.

RODE VLAGGEN (direct STERK_AF):
- Prijs per m2 perceel boven EUR 1200
- Projectmarge onder 5%
- Kleine percelen onder 150m2 in niet-centrale locatie
- Bruto huurrendement onder 2.5%

GROENE VLAGGEN (richting STERK_AAN):
- Perceel boven 500m2 op centrale locatie
- Prijs duidelijk onder marktwaarde (prijs/m2 woning onder EUR 1200)
- Projectmarge boven 20%
- Bruto rendement boven 6%
- Sloopkandidaat (oud pand, groot perceel, goede ligging)

=== GEVRAAGDE ANALYSE ===
Antwoord ALLEEN met dit JSON formaat, geen andere tekst:
{{
  "aanbeveling": "STERK_AAN",
  "korte_uitleg": "Max 2 concrete zinnen met de hoofdreden waarom wel/niet interessant",
  "kansen": ["kans 1", "kans 2", "kans 3"],
  "risicos": ["risico 1", "risico 2"],
  "beste_strategie": "VERHUUR",
  "prioriteit": 7
}}

Mogelijke waarden:
- aanbeveling: STERK_AAN / AAN / NEUTRAAL / AF / STERK_AF
- beste_strategie: VERHUUR / SLOOP_HERBOUW / RENOVATIE_VERHUUR / DOORVERKOOP
- prioriteit: getal van 1 tot 10 (10 = onmiddellijk bezoeken!)"""

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
