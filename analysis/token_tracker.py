"""
Token Tracker
Bijhoudt hoeveel Groq tokens gebruikt zijn en hoeveel er nog over zijn.
Zorgt dat we nooit de limiet overschrijden.
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime, date

logger = logging.getLogger(__name__)

TOKEN_BESTAND = Path("token_gebruik.json")


def _laad_data() -> dict:
    if TOKEN_BESTAND.exists():
        with open(TOKEN_BESTAND) as f:
            return json.load(f)
    return {
        "dag": str(date.today()),
        "tokens_vandaag": 0,
        "minuut_window": [],   # Lijst van (timestamp, tokens) voor de laatste minuut
        "totaal_ooit": 0,
        "aanroepen_vandaag": 0,
    }


def _sla_op(data: dict):
    with open(TOKEN_BESTAND, "w") as f:
        json.dump(data, f, indent=2)


def registreer_gebruik(tokens_gebruikt: int):
    """Registreer token gebruik na een API call."""
    data = _laad_data()

    # Reset als nieuwe dag
    if data["dag"] != str(date.today()):
        data["dag"] = str(date.today())
        data["tokens_vandaag"] = 0
        data["aanroepen_vandaag"] = 0
        data["minuut_window"] = []

    nu = time.time()
    data["tokens_vandaag"] += tokens_gebruikt
    data["totaal_ooit"] += tokens_gebruikt
    data["aanroepen_vandaag"] += 1
    data["minuut_window"].append({"tijd": nu, "tokens": tokens_gebruikt})

    # Verwijder entries ouder dan 60 seconden
    data["minuut_window"] = [
        e for e in data["minuut_window"]
        if nu - e["tijd"] < 60
    ]

    _sla_op(data)


def tokens_in_laatste_minuut() -> int:
    """Hoeveel tokens zijn er in de laatste 60 seconden gebruikt?"""
    data = _laad_data()
    nu = time.time()
    return sum(e["tokens"] for e in data["minuut_window"] if nu - e["tijd"] < 60)


def tokens_vandaag() -> int:
    """Hoeveel tokens zijn er vandaag al gebruikt?"""
    data = _laad_data()
    if data["dag"] != str(date.today()):
        return 0
    return data["tokens_vandaag"]


def kan_aanroepen(geschatte_tokens: int, limiet_minuut: int, limiet_dag: int) -> tuple[bool, str]:
    """
    Checkt of we een API call kunnen doen zonder de limiet te overschrijden.
    Geeft (True/False, reden) terug.
    """
    minuut_gebruik = tokens_in_laatste_minuut()
    dag_gebruik = tokens_vandaag()

    if minuut_gebruik + geschatte_tokens > limiet_minuut * 0.85:  # 85% limiet voor veiligheid
        wacht = 60 - (time.time() % 60)
        return False, f"Minuut limiet bijna bereikt ({minuut_gebruik}/{limiet_minuut}), wacht {wacht:.0f}s"

    if dag_gebruik + geschatte_tokens > limiet_dag:
        return False, f"Daglimiet bereikt ({dag_gebruik}/{limiet_dag} tokens)"

    return True, "ok"


def budget_status(limiet_minuut: int, limiet_dag: int) -> dict:
    """Geeft een overzicht van het huidige tokenbudget."""
    minuut = tokens_in_laatste_minuut()
    dag = tokens_vandaag()
    data = _laad_data()

    return {
        "minuut_gebruikt": minuut,
        "minuut_over": max(0, limiet_minuut - minuut),
        "minuut_pct": round(minuut / limiet_minuut * 100, 1),
        "dag_gebruikt": dag,
        "dag_over": max(0, limiet_dag - dag),
        "dag_pct": round(dag / limiet_dag * 100, 1),
        "aanroepen_vandaag": data.get("aanroepen_vandaag", 0),
    }
