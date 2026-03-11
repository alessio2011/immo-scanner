# ============================================================
# IMMO SCANNER - UITGEBREIDE INSTELLINGEN (config2.py)
# config.py wordt NOOIT aangeraakt
# Hier staan alle nieuwe/extra instellingen
# ============================================================

# --- TOKEN BUDGET (Groq gratis plan) ---
# Groq gratis: 6000 tokens/minuut, 500.000 tokens/dag
TOKENS_PER_MINUUT_LIMIET = 6000     # Veilige limiet (officieel 6000/min)
TOKENS_PER_DAG_LIMIET    = 450_000  # Veilige limiet (officieel 500k/dag)

# Geschatte tokenkosten per stap
TOKENS_SNELLE_CHECK   = 400   # Stap 1: alleen cijfers beoordelen (goedkoop)
TOKENS_LOCATIE_CHECK  = 600   # Stap 2: locatie + Wikipedia erbij
TOKENS_FOTO_ANALYSE   = 500   # Stap 3: foto's analyseren
TOKENS_VOLLEDIGE_AI   = 1200  # Stap 4: volledige diepgaande analyse

# Minimale score na snelle check om door te gaan naar volgende stap
DREMPEL_SNELLE_CHECK  = 50    # Score /100 na stap 1
DREMPEL_LOCATIE_CHECK = 60    # Score /100 na stap 2

# --- AI MODEL KEUZE ---
# Goedkoop snel model voor snelle checks
GROQ_MODEL_SNEL    = "llama-3.1-8b-instant"    # Weinig tokens, snel
# Krachtig model voor volledige analyse
GROQ_MODEL_KRACHTIG = "llama-3.3-70b-versatile" # Meer tokens, beter

# --- WACHTRIJ PRIORITEIT ---
# Panden met hogere score krijgen voorrang in de wachtrij
PRIORITEER_WACHTRIJ = True

# --- LOGGING ---
TOKEN_LOG_BESTAND = "token_gebruik.json"
