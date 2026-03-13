# ============================================================
# IMMO SCANNER - UITGEBREIDE INSTELLINGEN (config2.py)
# config.py wordt NOOIT aangeraakt
# Hier staan alle nieuwe/extra instellingen
# ============================================================

# --- AI MODEL KEUZE ---
# Primair: Gemini Flash 2.0 (gratis, 1.500 aanroepen/dag, sterk)
# Fallback: Groq als GEMINI_API_KEY niet ingesteld is in config.py
GEMINI_MODEL        = "gemini-2.0-flash"       # Primair model
GEMINI_MODEL_BACKUP = "gemini-1.5-flash"        # Backup bij overbelasting
GEMINI_MIN_INTERVAL = 4.5                       # Seconden tussen calls (gratis: 15/min)

# Groq modellen (fallback als geen Gemini key)
GROQ_MODEL_SNEL     = "llama-3.1-8b-instant"
GROQ_MODEL_KRACHTIG = "llama-3.3-70b-versatile"

# --- TOKEN BUDGET (alleen relevant als Groq gebruikt wordt) ---
TOKENS_PER_MINUUT_LIMIET = 6000
TOKENS_PER_DAG_LIMIET    = 450_000
TOKENS_SNELLE_CHECK      = 400
TOKENS_LOCATIE_CHECK     = 600
TOKENS_FOTO_ANALYSE      = 500
TOKENS_VOLLEDIGE_AI      = 1200
TOKENS_JURIDISCH         = 900

# Drempels voor Groq trechtersysteem
DREMPEL_SNELLE_CHECK  = 50
DREMPEL_LOCATIE_CHECK = 60

# --- WACHTRIJ ---
PRIORITEER_WACHTRIJ = True
MAX_PAGINAS         = 10   # Pagina's per postcode per scan

# --- LOGGING ---
TOKEN_LOG_BESTAND = "token_gebruik.json"

# --- GO / REVIEW / REJECT DREMPELS ---
DREMPEL_GO     = 75   # Totaalscore >= 75 → GO
DREMPEL_REVIEW = 60   # Totaalscore >= 60 → REVIEW
# < 60 → REJECT
