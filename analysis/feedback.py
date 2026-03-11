"""
Feedback & Leermodule
Slaat feedback op en genereert steeds betere lessen voor de AI.
Hoe meer feedback, hoe slimmer de AI wordt over tijd.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

FEEDBACK_BESTAND    = Path("feedback_data.json")
MAX_FEEDBACK_PROMPT = 12  # Meer voorbeelden = betere AI


def laad_feedback() -> list:
    if FEEDBACK_BESTAND.exists():
        with open(FEEDBACK_BESTAND, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def sla_feedback_op(pand: dict, metrics: dict, ai_analyse: dict, feedback: str):
    """feedback = 'goed' (👍) of 'slecht' (👎)"""
    alle = laad_feedback()
    alle.append({
        "datum":               datetime.now().isoformat(),
        "feedback":            feedback,
        "gemeente":            pand.get("gemeente", ""),
        "postcode":            pand.get("postcode", ""),
        "prijs":               pand.get("prijs", 0),
        "perceel_opp":         pand.get("perceel_opp", 0),
        "bewoonbare_opp":      pand.get("bewoonbare_opp", 0),
        "bouwjaar":            pand.get("bouwjaar", ""),
        "epc_score":           pand.get("epc_score", ""),
        "staat":               pand.get("staat", ""),
        "type":                pand.get("type", ""),
        "prijs_per_m2":        metrics.get("prijs_per_m2", 0),
        "prijs_per_m2_perceel":metrics.get("prijs_per_m2_perceel", 0),
        "bruto_rendement":     metrics.get("bruto_rendement", 0),
        "netto_rendement":     metrics.get("netto_rendement", 0),
        "project_marge":       metrics.get("project_marge", 0),
        "geschat_apps":        metrics.get("geschat_aantal_appartementen", 0),
        "renovatiekost":       metrics.get("renovatiekost", 0),
        "ai_aanbeveling":      ai_analyse.get("aanbeveling", ""),
        "ai_strategie":        ai_analyse.get("beste_strategie", ""),
        "ai_prioriteit":       ai_analyse.get("prioriteit", 0),
        "ai_uitleg":           ai_analyse.get("korte_uitleg", ""),
    })
    with open(FEEDBACK_BESTAND, "w", encoding="utf-8") as f:
        json.dump(alle, f, ensure_ascii=False, indent=2)
    logger.info(f"Feedback: {feedback} voor {pand.get('gemeente')} EUR {pand.get('prijs', 0):,}")


def genereer_lessen_voor_ai() -> str:
    """
    Genereert concrete lessen uit alle feedback.
    Hoe meer feedback, hoe gerichter de lessen.
    """
    alle = laad_feedback()
    if not alle:
        return ""

    goed   = [f for f in alle if f["feedback"] == "goed"]
    slecht = [f for f in alle if f["feedback"] == "slecht"]

    r = [f"=== LESSEN UIT {len(alle)} BEOORDELINGEN ==="]
    r.append(f"👍 {len(goed)} goedgekeurd | 👎 {len(slecht)} afgekeurd")
    r.append("")

    def gem(lst, key):
        vals = [x[key] for x in lst if x.get(key)]
        return sum(vals) / len(vals) if vals else 0

    if goed:
        r.append("✅ GOEDGEKEURDE PANDEN — gemiddeld:")
        r.append(f"  Prijs/m2: EUR {gem(goed,'prijs_per_m2'):.0f} | Perceel/m2: EUR {gem(goed,'prijs_per_m2_perceel'):.0f}")
        r.append(f"  Rendement: {gem(goed,'bruto_rendement'):.1f}% bruto / {gem(goed,'netto_rendement'):.1f}% netto")
        r.append(f"  Projectmarge: {gem(goed,'project_marge'):.1f}% | Gem apps: {gem(goed,'geschat_apps'):.1f}")
        gemeenten = list(set(p["gemeente"] for p in goed if p["gemeente"]))[:6]
        if gemeenten:
            r.append(f"  Interessante gemeenten: {', '.join(gemeenten)}")

        # Beste strategieën
        strategieen = {}
        for p in goed:
            s = p.get("ai_strategie", "")
            if s:
                strategieen[s] = strategieen.get(s, 0) + 1
        if strategieen:
            beste = sorted(strategieen.items(), key=lambda x: x[1], reverse=True)
            r.append(f"  Beste strategieën: {' > '.join(f'{s}({n}x)' for s,n in beste)}")

    if slecht:
        r.append("")
        r.append("❌ AFGEKEURDE PANDEN — gemiddeld:")
        r.append(f"  Prijs/m2: EUR {gem(slecht,'prijs_per_m2'):.0f} | Rendement: {gem(slecht,'bruto_rendement'):.1f}%")
        gemeenten = list(set(p["gemeente"] for p in slecht if p["gemeente"]))[:6]
        if gemeenten:
            r.append(f"  Minder interessante gemeenten: {', '.join(gemeenten)}")
        # Redenen van afkeuring
        uitleg = [p["ai_uitleg"] for p in slecht if p.get("ai_uitleg")][:3]
        for u in uitleg:
            r.append(f"  Reden: {u}")

    # Drempelwaarden afleiden uit feedback
    if len(goed) >= 3 and len(slecht) >= 3:
        r.append("")
        r.append("📐 AFGELEID UIT JOUW FEEDBACK:")
        min_rend_goed   = min(p["bruto_rendement"] for p in goed if p.get("bruto_rendement"))
        max_pm2_goed    = max(p["prijs_per_m2"] for p in goed if p.get("prijs_per_m2"))
        min_marge_goed  = min(p["project_marge"] for p in goed if p.get("project_marge"))
        r.append(f"  Minimaal rendement goedgekeurd: {min_rend_goed:.1f}%")
        r.append(f"  Maximale prijs/m2 goedgekeurd: EUR {max_pm2_goed:.0f}")
        r.append(f"  Minimale projectmarge goedgekeurd: {min_marge_goed:.1f}%")

    # Recente concrete voorbeelden
    recente = sorted(alle, key=lambda x: x["datum"], reverse=True)[:MAX_FEEDBACK_PROMPT]
    r.append("")
    r.append("🕐 RECENTE VOORBEELDEN (meest recent eerst):")
    for f in recente:
        sym = "👍" if f["feedback"] == "goed" else "👎"
        r.append(
            f"  {sym} {f['gemeente']} EUR {f['prijs']:,} | "
            f"{f['prijs_per_m2']:.0f}EUR/m2 | "
            f"{f['bruto_rendement']:.1f}% rendement | "
            f"marge {f['project_marge']:.1f}% | "
            f"prio {f.get('ai_prioriteit',0)}/10"
        )

    r.append("")
    r.append("Pas uw beoordeling aan op bovenstaande voorkeuren van deze investeerder.")
    return "\n".join(r)


def haal_pand_op_voor_feedback(pand_id: str) -> dict:
    bestand = Path(f"pending_feedback/{pand_id}.json")
    if bestand.exists():
        with open(bestand, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def sla_pand_op_voor_feedback(pand_id: str, pand: dict, metrics: dict, ai_analyse: dict):
    Path("pending_feedback").mkdir(exist_ok=True)
    with open(Path(f"pending_feedback/{pand_id}.json"), "w", encoding="utf-8") as f:
        json.dump({"pand": pand, "metrics": metrics, "ai_analyse": ai_analyse}, f, ensure_ascii=False)
