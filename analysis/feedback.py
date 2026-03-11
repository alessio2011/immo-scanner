"""
Feedback & Leermodule
Slaat feedback op over panden en gebruikt die om de AI te verbeteren.
Hoe meer feedback, hoe slimmer de AI wordt over tijd.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

FEEDBACK_BESTAND = Path("feedback_data.json")
MAX_FEEDBACK_IN_PROMPT = 8  # Hoeveel eerdere lessen meegeven aan AI


def laad_feedback() -> list:
    """Laadt alle opgeslagen feedback."""
    if FEEDBACK_BESTAND.exists():
        with open(FEEDBACK_BESTAND, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def sla_feedback_op(pand: dict, metrics: dict, ai_analyse: dict, feedback: str):
    """
    Slaat feedback op over een pand.
    feedback = "goed" (👍) of "slecht" (👎)
    """
    alle_feedback = laad_feedback()

    entry = {
        "datum": datetime.now().isoformat(),
        "feedback": feedback,  # "goed" of "slecht"
        "gemeente": pand.get("gemeente", ""),
        "postcode": pand.get("postcode", ""),
        "prijs": pand.get("prijs", 0),
        "perceel_opp": pand.get("perceel_opp", 0),
        "bewoonbare_opp": pand.get("bewoonbare_opp", 0),
        "bouwjaar": pand.get("bouwjaar", ""),
        "epc_score": pand.get("epc_score", ""),
        "prijs_per_m2": metrics.get("prijs_per_m2", 0),
        "prijs_per_m2_perceel": metrics.get("prijs_per_m2_perceel", 0),
        "bruto_rendement": metrics.get("bruto_rendement", 0),
        "project_marge": metrics.get("project_marge", 0),
        "ai_aanbeveling": ai_analyse.get("aanbeveling", ""),
        "ai_strategie": ai_analyse.get("beste_strategie", ""),
        "ai_uitleg": ai_analyse.get("korte_uitleg", ""),
    }

    alle_feedback.append(entry)

    with open(FEEDBACK_BESTAND, "w", encoding="utf-8") as f:
        json.dump(alle_feedback, f, ensure_ascii=False, indent=2)

    logger.info(f"Feedback opgeslagen: {feedback} voor {pand.get('gemeente')} EUR {pand.get('prijs', 0):,}")


def genereer_lessen_voor_ai() -> str:
    """
    Analyseert de feedback en genereert concrete lessen voor de AI.
    Geeft een tekst terug die in de AI prompt gezet wordt.
    """
    alle_feedback = laad_feedback()

    if not alle_feedback:
        return ""

    goede_panden = [f for f in alle_feedback if f["feedback"] == "goed"]
    slechte_panden = [f for f in alle_feedback if f["feedback"] == "slecht"]

    lessen = []
    lessen.append(f"=== LESSEN UIT EERDERE BEOORDELINGEN ({len(alle_feedback)} panden beoordeeld) ===")
    lessen.append(f"Goedgekeurd: {len(goede_panden)} panden | Afgekeurd: {len(slechte_panden)} panden")
    lessen.append("")

    # Analyseer patronen in goede panden
    if goede_panden:
        gem_prijs_m2_goed = sum(p["prijs_per_m2"] for p in goede_panden if p["prijs_per_m2"]) / max(len(goede_panden), 1)
        gem_rendement_goed = sum(p["bruto_rendement"] for p in goede_panden if p["bruto_rendement"]) / max(len(goede_panden), 1)
        gem_marge_goed = sum(p["project_marge"] for p in goede_panden if p["project_marge"]) / max(len(goede_panden), 1)
        goede_gemeenten = list(set(p["gemeente"] for p in goede_panden if p["gemeente"]))

        lessen.append("KENMERKEN VAN GOEDGEKEURDE PANDEN:")
        lessen.append(f"- Gemiddelde prijs/m2: EUR {gem_prijs_m2_goed:.0f}")
        lessen.append(f"- Gemiddeld bruto rendement: {gem_rendement_goed:.1f}%")
        lessen.append(f"- Gemiddelde projectmarge: {gem_marge_goed:.1f}%")
        if goede_gemeenten:
            lessen.append(f"- Interessante gemeenten: {', '.join(goede_gemeenten[:5])}")

    # Analyseer patronen in slechte panden
    if slechte_panden:
        gem_prijs_m2_slecht = sum(p["prijs_per_m2"] for p in slechte_panden if p["prijs_per_m2"]) / max(len(slechte_panden), 1)
        slechte_gemeenten = list(set(p["gemeente"] for p in slechte_panden if p["gemeente"]))

        lessen.append("")
        lessen.append("KENMERKEN VAN AFGEKEURDE PANDEN:")
        lessen.append(f"- Gemiddelde prijs/m2: EUR {gem_prijs_m2_slecht:.0f}")
        if slechte_gemeenten:
            lessen.append(f"- Minder interessante gemeenten: {', '.join(slechte_gemeenten[:5])}")

    # Voeg de laatste concrete voorbeelden toe
    recente_feedback = sorted(alle_feedback, key=lambda x: x["datum"], reverse=True)[:MAX_FEEDBACK_IN_PROMPT]
    lessen.append("")
    lessen.append("RECENTE CONCRETE VOORBEELDEN:")
    for f in recente_feedback:
        symbool = "👍" if f["feedback"] == "goed" else "👎"
        lessen.append(
            f"{symbool} {f['gemeente']} EUR {f['prijs']:,} | "
            f"{f['prijs_per_m2']:.0f} EUR/m2 | "
            f"{f['bruto_rendement']:.1f}% rendement | "
            f"marge {f['project_marge']:.1f}% | "
            f"AI zei: {f['ai_aanbeveling']}"
        )

    lessen.append("")
    lessen.append("Gebruik deze lessen om uw beoordeling te kalibreren op de voorkeuren van deze specifieke investeerder.")

    return "\n".join(lessen)


def haal_pand_op_voor_feedback(pand_id: str) -> dict:
    """Haalt een opgeslagen pand op via ID voor feedbackverwerking."""
    bestand = Path(f"pending_feedback/{pand_id}.json")
    if bestand.exists():
        with open(bestand, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def sla_pand_op_voor_feedback(pand_id: str, pand: dict, metrics: dict, ai_analyse: dict):
    """Slaat pand tijdelijk op zodat feedback later verwerkt kan worden."""
    Path("pending_feedback").mkdir(exist_ok=True)
    bestand = Path(f"pending_feedback/{pand_id}.json")
    with open(bestand, "w", encoding="utf-8") as f:
        json.dump({"pand": pand, "metrics": metrics, "ai_analyse": ai_analyse}, f, ensure_ascii=False)
