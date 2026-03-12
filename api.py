"""
Immo Scanner API
Simpele Flask API die de website van data voorziet.
Draait op de Pi naast scanner.py

Start: python3 api.py
Bereikbaar op: http://<pi-ip>:5000
"""

from flask import Flask, jsonify, request
from pathlib import Path
import json
from datetime import datetime

app = Flask(__name__)

GEZIEN_BESTAND   = Path("geziene_panden.json")
WACHTRIJ_BESTAND = Path("ai_wachtrij.json")
FEEDBACK_BESTAND = Path("feedback_data.json")
TOKEN_BESTAND    = Path("token_gebruik.json")
PENDING_DIR      = Path("pending_feedback")
LOG_BESTAND      = Path("immo_scanner.log")

def laad_json(pad, fallback):
    try:
        if pad.exists():
            with open(pad, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback

def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def dashboard():
    tokens = laad_json(TOKEN_BESTAND, {})
    wachtrij = laad_json(WACHTRIJ_BESTAND, [])
    gezien = laad_json(GEZIEN_BESTAND, {"ids": []})
    feedback = laad_json(FEEDBACK_BESTAND, [])

    # Haal alle panden op uit pending_feedback (dit zijn de geanalyseerde panden)
    panden = laad_alle_panden()

    vandaag = datetime.now().date().isoformat()
    vandaag_panden = [p for p in panden if p.get("datum", "")[:10] == vandaag]

    go_count     = len([p for p in vandaag_panden if p.get("beslissing") == "GO"])
    review_count = len([p for p in vandaag_panden if p.get("beslissing") == "REVIEW"])

    return cors(jsonify({
        "go":            go_count,
        "review":        review_count,
        "reject":        max(0, len(gezien.get("ids", [])) - go_count - review_count),
        "gescand":       len(gezien.get("ids", [])),
        "wachtrij":      len(wachtrij),
        "tokens_gebruikt": tokens.get("tokens_vandaag", 0),
        "tokens_limiet": 450000,
        "aanroepen":     tokens.get("aanroepen_vandaag", 0),
        "laatste_update": tokens.get("dag", ""),
    }))


# ─── PANDEN ───────────────────────────────────────────────────────────────────

def laad_alle_panden():
    """Laadt alle geanalyseerde panden uit pending_feedback map."""
    panden = []
    if not PENDING_DIR.exists():
        return panden
    for bestand in sorted(PENDING_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(bestand, encoding="utf-8") as f:
                data = json.load(f)
            pand    = data.get("pand", {})
            metrics = data.get("metrics", {})
            ai      = data.get("ai_analyse", {})
            panden.append({
                "id":            bestand.stem,
                "gemeente":      pand.get("gemeente", ""),
                "postcode":      pand.get("postcode", ""),
                "straat":        pand.get("straat", ""),
                "huisnummer":    pand.get("huisnummer", ""),
                "prijs":         pand.get("prijs", 0),
                "type":          pand.get("type", ""),
                "bewoonbare_opp":pand.get("bewoonbare_opp", 0),
                "perceel_opp":   pand.get("perceel_opp", 0),
                "slaapkamers":   pand.get("slaapkamers", 0),
                "bouwjaar":      pand.get("bouwjaar", ""),
                "epc_score":     pand.get("epc_score", ""),
                "staat":         pand.get("staat", ""),
                "foto_url":      pand.get("foto_url", ""),
                "url":           pand.get("url", ""),
                "bruto_rendement":    metrics.get("bruto_rendement", 0),
                "netto_rendement":    metrics.get("netto_rendement", 0),
                "project_marge":      metrics.get("project_marge", 0),
                "prijs_per_m2":       metrics.get("prijs_per_m2", 0),
                "prijs_per_m2_perceel":metrics.get("prijs_per_m2_perceel", 0),
                "totale_aankoopkost": metrics.get("totale_aankoopkost", 0),
                "geschat_apps":       metrics.get("geschat_aantal_appartementen", 0),
                "project_winst":      metrics.get("project_winst", 0),
                "totale_projectkosten":metrics.get("totale_projectkosten", 0),
                "geschatte_verkoopopbrengst": metrics.get("geschatte_verkoopopbrengst", 0),
                "renovatiekost":      metrics.get("renovatiekost", 0),
                "renovatie_type":     metrics.get("renovatie_type", ""),
                "aanbeveling":   ai.get("aanbeveling", "NEUTRAAL"),
                "beslissing":    ai.get("beslissing", "REVIEW"),
                "totale_score":  ai.get("totale_score", 0),
                "subscores":     ai.get("subscores", {}),
                "scenarios":     ai.get("scenarios", {}),
                "zachte_vlaggen":ai.get("zachte_vlaggen", []),
                "korte_uitleg":  ai.get("korte_uitleg", ""),
                "kansen":        ai.get("kansen", []),
                "risicos":       ai.get("risicos", []),
                "beste_strategie": ai.get("beste_strategie", ""),
                "prioriteit":    ai.get("prioriteit", 5),
                "datum":         datetime.fromtimestamp(bestand.stat().st_mtime).isoformat(),
            })
        except Exception:
            continue
    return panden


@app.route("/api/panden")
def panden():
    beslissing = request.args.get("beslissing", "")
    alle = laad_alle_panden()
    if beslissing:
        alle = [p for p in alle if p.get("beslissing") == beslissing]
    return cors(jsonify(alle))


@app.route("/api/pand/<pand_id>")
def pand_detail(pand_id):
    bestand = PENDING_DIR / f"{pand_id}.json"
    if not bestand.exists():
        return cors(jsonify({"fout": "Pand niet gevonden"})), 404
    with open(bestand, encoding="utf-8") as f:
        data = json.load(f)
    return cors(jsonify(data))


# ─── FEEDBACK ─────────────────────────────────────────────────────────────────

@app.route("/api/feedback", methods=["POST", "OPTIONS"])
def feedback():
    if request.method == "OPTIONS":
        return cors(jsonify({}))
    data = request.get_json()
    pand_id  = data.get("pand_id")
    ftype    = data.get("feedback")  # "goed" of "slecht"

    if not pand_id or ftype not in ["goed", "slecht"]:
        return cors(jsonify({"fout": "Ongeldige data"})), 400

    bestand = PENDING_DIR / f"{pand_id}.json"
    if not bestand.exists():
        return cors(jsonify({"fout": "Pand niet gevonden"})), 404

    with open(bestand, encoding="utf-8") as f:
        pand_data = json.load(f)

    # Sla feedback op via feedback module
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from analysis.feedback import sla_feedback_op
    sla_feedback_op(
        pand_data["pand"],
        pand_data["metrics"],
        pand_data["ai_analyse"],
        ftype
    )
    return cors(jsonify({"ok": True}))


# ─── STATISTIEKEN ─────────────────────────────────────────────────────────────

@app.route("/api/stats")
def stats():
    panden   = laad_alle_panden()
    feedback = laad_json(FEEDBACK_BESTAND, [])

    go_panden     = [p for p in panden if p.get("beslissing") == "GO"]
    review_panden = [p for p in panden if p.get("beslissing") == "REVIEW"]

    # Top gemeenten
    gemeente_count = {}
    for p in go_panden:
        g = p.get("gemeente", "")
        if g:
            gemeente_count[g] = gemeente_count.get(g, 0) + 1
    top_gemeenten = sorted(gemeente_count.items(), key=lambda x: x[1], reverse=True)[:6]

    # Score verdeling
    score_buckets = {"<40":0,"40-50":0,"50-60":0,"60-70":0,"70-80":0,"80-90":0,">90":0}
    for p in panden:
        s = p.get("totale_score", 0)
        if s < 40: score_buckets["<40"] += 1
        elif s < 50: score_buckets["40-50"] += 1
        elif s < 60: score_buckets["50-60"] += 1
        elif s < 70: score_buckets["60-70"] += 1
        elif s < 80: score_buckets["70-80"] += 1
        elif s < 90: score_buckets["80-90"] += 1
        else: score_buckets[">90"] += 1

    gem_score_go = round(sum(p.get("totale_score",0) for p in go_panden) / max(len(go_panden),1), 1)

    return cors(jsonify({
        "totaal":        len(panden),
        "go":            len(go_panden),
        "review":        len(review_panden),
        "go_rate":       round(len(go_panden)/max(len(panden),1)*100, 1),
        "gem_score_go":  gem_score_go,
        "feedback_goed": len([f for f in feedback if f.get("feedback")=="goed"]),
        "feedback_slecht":len([f for f in feedback if f.get("feedback")=="slecht"]),
        "top_gemeenten": top_gemeenten,
        "score_verdeling": score_buckets,
    }))


# ─── LOGS ─────────────────────────────────────────────────────────────────────

@app.route("/api/logs")
def logs():
    try:
        with open(LOG_BESTAND, encoding="utf-8") as f:
            regels = f.readlines()
        laatste = [r.strip() for r in regels[-50:] if r.strip()]
        return cors(jsonify({"logs": laatste}))
    except Exception:
        return cors(jsonify({"logs": []}))


if __name__ == "__main__":
    print("Immo Scanner API draait op http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
