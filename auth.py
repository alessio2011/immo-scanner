"""
Auth module — multi-user systeem voor Immo Scanner
Beheert: registratie, login, sessies, config per gebruiker
Opslag: users/users.json + users/sessions.json (geen database nodig)
"""

import json
import uuid
import hashlib
import hmac
import time
import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

USERS_DIR      = Path("users")
USERS_BESTAND  = USERS_DIR / "users.json"
SESSIES_BESTAND= USERS_DIR / "sessions.json"
PANDEN_DIR     = USERS_DIR / "panden"

USERS_DIR.mkdir(exist_ok=True)
PANDEN_DIR.mkdir(exist_ok=True)

# Sessie geldig voor 30 dagen
SESSIE_DUUR_SECONDEN = 30 * 24 * 3600

# ─── STANDAARD CONFIG PER GEBRUIKER ──────────────────────────────────────────

STANDAARD_CONFIG = {
    "postcodes": [],
    "max_prijs": 600000,
    "min_prijs": 0,
    "min_rendement": 3.5,
    "drempel_go": 75,
    "drempel_review": 60,
    "max_paginas": 10,
    "scan_interval_minuten": 30,
    "telegram_chat_id": "",
    "telegram_actief": False,
    "strategie_voorkeur": [],       # bv. ["SLOOP_HERBOUW", "VERHUUR"]
    "min_perceel_opp": 0,
    "max_bouwjaar": 9999,
    "notificaties_go": True,
    "notificaties_review": True,
    "onboarding_gedaan": False,
}

# ─── WACHTWOORD HASHING ───────────────────────────────────────────────────────

def _hash_wachtwoord(wachtwoord: str, salt: str = None) -> tuple[str, str]:
    """Geeft (hash, salt) terug."""
    if salt is None:
        salt = uuid.uuid4().hex
    h = hashlib.pbkdf2_hmac("sha256", wachtwoord.encode(), salt.encode(), 260000)
    return h.hex(), salt

def _check_wachtwoord(wachtwoord: str, opgeslagen_hash: str, salt: str) -> bool:
    h, _ = _hash_wachtwoord(wachtwoord, salt)
    return hmac.compare_digest(h, opgeslagen_hash)


# ─── OPSLAG HULPFUNCTIES ─────────────────────────────────────────────────────

def _laad_users() -> dict:
    try:
        if USERS_BESTAND.exists():
            with open(USERS_BESTAND, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _sla_users_op(users: dict):
    with open(USERS_BESTAND, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def _laad_sessies() -> dict:
    try:
        if SESSIES_BESTAND.exists():
            with open(SESSIES_BESTAND, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _sla_sessies_op(sessies: dict):
    with open(SESSIES_BESTAND, "w", encoding="utf-8") as f:
        json.dump(sessies, f, ensure_ascii=False, indent=2)


# ─── REGISTRATIE ─────────────────────────────────────────────────────────────

def registreer(email: str, wachtwoord: str, naam: str) -> tuple[bool, str]:
    """
    Registreert een nieuwe gebruiker.
    Geeft (success, bericht_of_user_id) terug.
    """
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Ongeldig e-mailadres"
    if len(wachtwoord) < 6:
        return False, "Wachtwoord moet minstens 6 tekens zijn"
    if not naam.strip():
        return False, "Naam is verplicht"

    users = _laad_users()
    # Check of e-mail al bestaat
    for u in users.values():
        if u["email"] == email:
            return False, "E-mailadres al in gebruik"

    user_id = uuid.uuid4().hex
    pw_hash, salt = _hash_wachtwoord(wachtwoord)

    users[user_id] = {
        "user_id":   user_id,
        "email":     email,
        "naam":      naam.strip(),
        "pw_hash":   pw_hash,
        "salt":      salt,
        "aangemaakt": datetime.now().isoformat(),
        "rol":       "user",   # "user" of "admin"
        "config":    STANDAARD_CONFIG.copy(),
    }
    _sla_users_op(users)
    logger.info(f"Nieuwe gebruiker: {email} ({user_id[:8]})")
    return True, user_id


# ─── LOGIN ───────────────────────────────────────────────────────────────────

def login(email: str, wachtwoord: str) -> tuple[bool, str]:
    """
    Logt een gebruiker in.
    Geeft (success, sessie_token_of_foutbericht) terug.
    """
    email = email.strip().lower()
    users = _laad_users()

    user = None
    user_id = None
    for uid, u in users.items():
        if u["email"] == email:
            user = u
            user_id = uid
            break

    if not user:
        return False, "E-mailadres of wachtwoord incorrect"

    if not _check_wachtwoord(wachtwoord, user["pw_hash"], user["salt"]):
        return False, "E-mailadres of wachtwoord incorrect"

    # Sessie aanmaken
    sessie_token = uuid.uuid4().hex
    sessies = _laad_sessies()
    sessies[sessie_token] = {
        "user_id":   user_id,
        "aangemaakt": time.time(),
        "verloopt":  time.time() + SESSIE_DUUR_SECONDEN,
    }
    _sla_sessies_op(sessies)
    logger.info(f"Login: {email}")
    return True, sessie_token


# ─── SESSIE VALIDEREN ─────────────────────────────────────────────────────────

def valideer_sessie(token: str) -> dict | None:
    """
    Valideert een sessie token.
    Geeft de user dict terug, of None als ongeldig/verlopen.
    """
    if not token:
        return None
    sessies = _laad_sessies()
    sessie = sessies.get(token)
    if not sessie:
        return None
    if time.time() > sessie["verloopt"]:
        # Sessie verlopen — opruimen
        del sessies[token]
        _sla_sessies_op(sessies)
        return None

    users = _laad_users()
    return users.get(sessie["user_id"])


def haal_user_op(token: str) -> dict | None:
    """Zelfde als valideer_sessie — voor leesbaarheid."""
    return valideer_sessie(token)


# ─── CONFIG BEHEER ───────────────────────────────────────────────────────────

def haal_config_op(token: str) -> dict | None:
    """Geeft de config van de ingelogde gebruiker terug."""
    user = valideer_sessie(token)
    if not user:
        return None
    return user.get("config", STANDAARD_CONFIG.copy())


def update_config(token: str, nieuwe_config: dict) -> tuple[bool, str]:
    """Slaat de config van een gebruiker op."""
    user = valideer_sessie(token)
    if not user:
        return False, "Niet ingelogd"

    users = _laad_users()
    user_id = user["user_id"]
    if user_id not in users:
        return False, "Gebruiker niet gevonden"

    # Merge — alleen bekende velden updaten
    huidig = users[user_id].get("config", STANDAARD_CONFIG.copy())
    for k, v in nieuwe_config.items():
        if k in STANDAARD_CONFIG:
            huidig[k] = v

    users[user_id]["config"] = huidig
    _sla_users_op(users)
    return True, "Config opgeslagen"


def sla_onboarding_op(token: str, onboarding_data: dict) -> tuple[bool, str]:
    """
    Verwerkt onboarding antwoorden en zet de config.
    onboarding_data: {
        regio: "Hasselt" / "Genk" / ...,
        postcodes: ["3500","3510",...],
        budget_max: 500000,
        strategie: ["SLOOP_HERBOUW","VERHUUR"],
        min_rendement: 4.0,
        telegram_chat_id: "-123456789" of "",
    }
    """
    user = valideer_sessie(token)
    if not user:
        return False, "Niet ingelogd"

    config = user.get("config", STANDAARD_CONFIG.copy())
    config["postcodes"]          = onboarding_data.get("postcodes", [])
    config["max_prijs"]          = onboarding_data.get("budget_max", 600000)
    config["min_rendement"]      = onboarding_data.get("min_rendement", 3.5)
    config["strategie_voorkeur"] = onboarding_data.get("strategie", [])
    config["telegram_chat_id"]   = onboarding_data.get("telegram_chat_id", "")
    config["telegram_actief"]    = bool(onboarding_data.get("telegram_chat_id", ""))
    config["onboarding_gedaan"]  = True

    return update_config(token, config)


# ─── LOGOUT ──────────────────────────────────────────────────────────────────

def logout(token: str):
    """Verwijdert de sessie."""
    sessies = _laad_sessies()
    if token in sessies:
        del sessies[token]
        _sla_sessies_op(sessies)


# ─── PANDEN PER GEBRUIKER ────────────────────────────────────────────────────

def sla_pand_op_voor_user(user_id: str, pand_id: str, data: dict):
    """Slaat een geanalyseerd pand op voor een specifieke gebruiker."""
    user_dir = PANDEN_DIR / user_id
    user_dir.mkdir(exist_ok=True)
    with open(user_dir / f"{pand_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def laad_panden_van_user(user_id: str) -> list:
    """Laadt alle panden van een gebruiker."""
    user_dir = PANDEN_DIR / user_id
    if not user_dir.exists():
        return []
    panden = []
    for bestand in sorted(user_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(bestand, encoding="utf-8") as f:
                panden.append(json.load(f))
        except Exception:
            continue
    return panden

def laad_alle_users() -> dict:
    """Admin: alle gebruikers ophalen (zonder wachtwoorden)."""
    users = _laad_users()
    return {
        uid: {k: v for k, v in u.items() if k not in ("pw_hash", "salt")}
        for uid, u in users.items()
    }

def opruimen_verlopen_sessies():
    """Ruimt verlopen sessies op — roep periodiek aan."""
    sessies = _laad_sessies()
    nu = time.time()
    voor = len(sessies)
    sessies = {t: s for t, s in sessies.items() if s["verloopt"] > nu}
    if len(sessies) < voor:
        _sla_sessies_op(sessies)
