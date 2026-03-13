"""
Immovate API — Multi-user versie
Alle endpoints zijn beveiligd met sessie tokens (behalve /auth/*)

Start: python3 api.py
Bereikbaar via Cloudflare Tunnel op je eigen domein
"""

from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
from pathlib import Path
import json
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config2
from auth import (
    registreer, login, logout, valideer_sessie,
    haal_config_op, update_config, sla_onboarding_op,
    laad_alle_users, opruimen_verlopen_sessies, STANDAARD_CONFIG
)

WEBSITE_DIR = Path(__file__).parent / "website"

app = Flask(__name__, static_folder=None)
CORS(app)  # GitHub Pages → Pi tunnel: alle origins toelaten

GEZIEN_BESTAND   = Path("geziene_panden.json")
WACHTRIJ_BESTAND = Path("ai_wachtrij.json")
TOKEN_BESTAND    = Path("token_gebruik.json")
LOG_BESTAND      = Path("immo_scanner.log")
PENDING_DIR      = Path("pending_feedback")


# ─── WEBSITE SERVEREN ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(WEBSITE_DIR, "index.html")

@app.route("/<path:bestand>")
def statisch(bestand):
    """Serveer statische bestanden uit de website map (CSS, JS, afbeeldingen)."""
    if (WEBSITE_DIR / bestand).exists():
        return send_from_directory(WEBSITE_DIR, bestand)
    # Geen statisch bestand — geef index terug (SPA fallback)
    return send_from_directory(WEBSITE_DIR, "index.html")


# ─── CORS + AUTH HELPERS ─────────────────────────────────────────────────────

def cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    return response

def haal_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("immo_token", "")

def vereist_login():
    token = haal_token()
    user = valideer_sessie(token)
    if not user:
        return None, cors(make_response(jsonify({"fout": "Niet ingelogd", "code": "AUTH_REQUIRED"}), 401))
    return user, None

def laad_json(pad, fallback):
    try:
        if Path(pad).exists():
            with open(pad, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return fallback


@app.route("/api/<path:pad>", methods=["OPTIONS"])
def options_handler(pad):
    return cors(make_response("", 204))

@app.route("/auth/<path:pad>", methods=["OPTIONS"])
def options_auth(pad):
    return cors(make_response("", 204))


# ─── AUTH ────────────────────────────────────────────────────────────────────

@app.route("/auth/registreer", methods=["POST"])
def auth_registreer():
    data = request.get_json() or {}
    ok, resultaat = registreer(data.get("email",""), data.get("wachtwoord",""), data.get("naam",""))
    if not ok:
        return cors(jsonify({"fout": resultaat})), 400
    ok2, token = login(data.get("email",""), data.get("wachtwoord",""))
    if not ok2:
        return cors(jsonify({"fout": "Login na registratie mislukt"})), 500
    user = valideer_sessie(token)
    resp = make_response(jsonify({
        "token": token, "user_id": user["user_id"],
        "naam": user["naam"], "email": user["email"],
        "onboarding_gedaan": user["config"].get("onboarding_gedaan", False),
    }), 201)
    resp.set_cookie("immo_token", token, max_age=30*24*3600, httponly=True, samesite="Lax")
    return cors(resp)


@app.route("/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json() or {}
    ok, resultaat = login(data.get("email",""), data.get("wachtwoord",""))
    if not ok:
        return cors(jsonify({"fout": resultaat})), 401
    token = resultaat
    user = valideer_sessie(token)
    resp = make_response(jsonify({
        "token": token, "user_id": user["user_id"],
        "naam": user["naam"], "email": user["email"],
        "onboarding_gedaan": user["config"].get("onboarding_gedaan", False),
    }))
    resp.set_cookie("immo_token", token, max_age=30*24*3600, httponly=True, samesite="Lax")
    return cors(resp)


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    logout(haal_token())
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("immo_token")
    return cors(resp)


@app.route("/auth/mij", methods=["GET"])
def auth_mij():
    user, fout = vereist_login()
    if fout: return fout
    return cors(jsonify({
        "user_id": user["user_id"], "naam": user["naam"],
        "email": user["email"], "rol": user.get("rol","user"),
        "onboarding_gedaan": user["config"].get("onboarding_gedaan", False),
        "config": user.get("config", {}),
    }))


# ─── ONBOARDING ──────────────────────────────────────────────────────────────

@app.route("/api/onboarding", methods=["POST"])
def onboarding():
    user, fout = vereist_login()
    if fout: return fout
    ok, bericht = sla_onboarding_op(haal_token(), request.get_json() or {})
    if not ok:
        return cors(jsonify({"fout": bericht})), 400
    return cors(jsonify({"ok": True}))


# ─── CONFIG ──────────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def get_config():
    user, fout = vereist_login()
    if fout: return fout
    return cors(jsonify(user.get("config", STANDAARD_CONFIG)))

@app.route("/api/config", methods=["POST"])
def set_config():
    user, fout = vereist_login()
    if fout: return fout
    ok, bericht = update_config(haal_token(), request.get_json() or {})
    if not ok:
        return cors(jsonify({"fout": bericht})), 400
    return cors(jsonify({"ok": True}))


# ─── PANDEN HELPERS ──────────────────────────────────────────────────────────

def _laad_globale_panden():
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
                "id": bestand.stem,
                "gemeente": pand.get("gemeente",""), "postcode": pand.get("postcode",""),
                "straat": pand.get("straat",""), "huisnummer": pand.get("huisnummer",""),
                "prijs": pand.get("prijs",0), "type": pand.get("type",""),
                "bewoonbare_opp": pand.get("bewoonbare_opp",0), "perceel_opp": pand.get("perceel_opp",0),
                "slaapkamers": pand.get("slaapkamers",0), "bouwjaar": pand.get("bouwjaar",""),
                "epc_score": pand.get("epc_score",""), "staat": pand.get("staat",""),
                "foto_url": pand.get("foto_url",""), "url": pand.get("url",""),
                "bruto_rendement": metrics.get("bruto_rendement",0),
                "netto_rendement": metrics.get("netto_rendement",0),
                "project_marge": metrics.get("project_marge",0),
                "prijs_per_m2": metrics.get("prijs_per_m2",0),
                "prijs_per_m2_perceel": metrics.get("prijs_per_m2_perceel",0),
                "totale_aankoopkost": metrics.get("totale_aankoopkost",0),
                "geschat_apps": metrics.get("geschat_aantal_appartementen",0),
                "project_winst": metrics.get("project_winst",0),
                "renovatiekost": metrics.get("renovatiekost",0),
                "aanbeveling": ai.get("aanbeveling","NEUTRAAL"),
                "beslissing": ai.get("beslissing","REVIEW"),
                "totale_score": ai.get("totale_score",0),
                "subscores": ai.get("subscores",{}), "scenarios": ai.get("scenarios",{}),
                "zachte_vlaggen": ai.get("zachte_vlaggen",[]),
                "korte_uitleg": ai.get("korte_uitleg",""),
                "kansen": ai.get("kansen",[]), "risicos": ai.get("risicos",[]),
                "beste_strategie": ai.get("beste_strategie",""),
                "prioriteit": ai.get("prioriteit",5),
                "juridisch": ai.get("juridisch",None),
                "datum": datetime.fromtimestamp(bestand.stat().st_mtime).isoformat(),
            })
        except Exception:
            continue
    return panden


def _filter_voor_user(panden, user):
    config = user.get("config", {})
    postcodes = set(str(p) for p in config.get("postcodes", []))
    strategie = config.get("strategie_voorkeur", [])
    if postcodes:
        panden = [p for p in panden if str(p.get("postcode","")) in postcodes]
    if strategie:
        panden = [p for p in panden if p.get("beste_strategie","") in strategie]
    return panden


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def dashboard():
    user, fout = vereist_login()
    if fout: return fout
    tokens   = laad_json(TOKEN_BESTAND, {})
    wachtrij = laad_json(WACHTRIJ_BESTAND, [])
    gezien   = laad_json(GEZIEN_BESTAND, {"ids": []})
    panden   = _filter_voor_user(_laad_globale_panden(), user)
    vandaag  = datetime.now().date().isoformat()
    vd = [p for p in panden if p.get("datum","")[:10] == vandaag]
    return cors(jsonify({
        "go":              len([p for p in vd if p.get("beslissing")=="GO"]),
        "review":          len([p for p in vd if p.get("beslissing")=="REVIEW"]),
        "reject":          max(0, len(gezien.get("ids",[]))-len(vd)),
        "gescand":         len(gezien.get("ids",[])),
        "wachtrij":        len(wachtrij),
        "tokens_gebruikt": tokens.get("tokens_vandaag",0),
        "tokens_limiet":   450000,
        "aanroepen":       tokens.get("aanroepen_vandaag",0),
        "naam":            user["naam"],
    }))


# ─── PANDEN ──────────────────────────────────────────────────────────────────

@app.route("/api/panden")
def panden_endpoint():
    user, fout = vereist_login()
    if fout: return fout
    beslissing = request.args.get("beslissing","")
    alle = _filter_voor_user(_laad_globale_panden(), user)
    if beslissing:
        alle = [p for p in alle if p.get("beslissing")==beslissing]
    return cors(jsonify(alle))


@app.route("/api/pand/<pand_id>")
def pand_detail(pand_id):
    user, fout = vereist_login()
    if fout: return fout
    bestand = PENDING_DIR / f"{pand_id}.json"
    if not bestand.exists():
        return cors(jsonify({"fout": "Niet gevonden"})), 404
    with open(bestand, encoding="utf-8") as f:
        return cors(jsonify(json.load(f)))


# ─── FEEDBACK ────────────────────────────────────────────────────────────────

@app.route("/api/feedback", methods=["POST"])
def feedback():
    user, fout = vereist_login()
    if fout: return fout
    data = request.get_json() or {}
    pand_id = data.get("pand_id")
    ftype   = data.get("feedback")
    if not pand_id or ftype not in ["goed","slecht"]:
        return cors(jsonify({"fout": "Ongeldige data"})), 400
    bestand = PENDING_DIR / f"{pand_id}.json"
    if not bestand.exists():
        return cors(jsonify({"fout": "Niet gevonden"})), 404
    with open(bestand, encoding="utf-8") as f:
        pd = json.load(f)
    from analysis.feedback import sla_feedback_op
    sla_feedback_op(pd["pand"], pd["metrics"], pd["ai_analyse"], ftype)
    return cors(jsonify({"ok": True}))


# ─── STATS ───────────────────────────────────────────────────────────────────

@app.route("/api/stats")
def stats():
    user, fout = vereist_login()
    if fout: return fout
    panden = _filter_voor_user(_laad_globale_panden(), user)
    feedback_data = laad_json(Path("feedback_data.json"), [])
    go = [p for p in panden if p.get("beslissing")=="GO"]
    gemeente_count = {}
    for p in go:
        g = p.get("gemeente","")
        if g: gemeente_count[g] = gemeente_count.get(g,0)+1
    buckets = {"<40":0,"40-50":0,"50-60":0,"60-70":0,"70-80":0,"80-90":0,">90":0}
    for p in panden:
        s = p.get("totale_score",0)
        if s<40: buckets["<40"]+=1
        elif s<50: buckets["40-50"]+=1
        elif s<60: buckets["50-60"]+=1
        elif s<70: buckets["60-70"]+=1
        elif s<80: buckets["70-80"]+=1
        elif s<90: buckets["80-90"]+=1
        else: buckets[">90"]+=1
    return cors(jsonify({
        "totaal": len(panden), "go": len(go),
        "review": len([p for p in panden if p.get("beslissing")=="REVIEW"]),
        "go_rate": round(len(go)/max(len(panden),1)*100,1),
        "gem_score_go": round(sum(p.get("totale_score",0) for p in go)/max(len(go),1),1),
        "feedback_goed": len([f for f in feedback_data if f.get("feedback")=="goed"]),
        "feedback_slecht": len([f for f in feedback_data if f.get("feedback")=="slecht"]),
        "top_gemeenten": sorted(gemeente_count.items(), key=lambda x:x[1], reverse=True)[:6],
        "score_verdeling": buckets,
    }))


# ─── LOGS ────────────────────────────────────────────────────────────────────

@app.route("/api/logs")
def logs():
    user, fout = vereist_login()
    if fout: return fout
    try:
        with open(LOG_BESTAND, encoding="utf-8") as f:
            regels = f.readlines()
        return cors(jsonify({"logs": [r.strip() for r in regels[-100:] if r.strip()]}))
    except Exception:
        return cors(jsonify({"logs": []}))


# ─── ADMIN ───────────────────────────────────────────────────────────────────

@app.route("/api/admin/users")
def admin_users():
    user, fout = vereist_login()
    if fout: return fout
    if user.get("rol") != "admin":
        return cors(jsonify({"fout": "Geen toegang"})), 403
    return cors(jsonify(laad_alle_users()))


# ─── START ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("🏠 Immovate API — multi-user")
    print("   http://0.0.0.0:5000")
    print("=" * 50)
    from auth import _laad_users, _sla_users_op
    if not _laad_users():
        ok, uid = registreer("admin@immovate.be", "admin123", "Admin")
        if ok:
            users = _laad_users()
            users[uid]["rol"] = "admin"
            _sla_users_op(users)
            print("✅ Admin: admin@immovate.be / admin123  ← verander dit wachtwoord!")
    app.run(host="0.0.0.0", port=5000, debug=False)
