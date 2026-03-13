# ============================================================
# IMMOVATE — SCANNER INSTELLINGEN
# Pas dit gerust aan — geen geheimen hier
# ============================================================

# --- AI MODELLEN ---
# Gemini (primair, gratis)
GEMINI_MODEL        = "gemini-2.0-flash"    # Primair model
GEMINI_MODEL_BACKUP = "gemini-1.5-flash"    # Backup bij overbelasting
GEMINI_MIN_INTERVAL = 4.5                   # Seconden tussen calls (gratis: 15/min)

# Groq (fallback)
GROQ_MODEL_SNEL     = "llama-3.1-8b-instant"
GROQ_MODEL_KRACHTIG = "llama-3.3-70b-versatile"

# --- SCAN GEDRAG ---
MAX_PAGINAS         = 10      # Pagina's per postcode per scan (10 ≈ 300 panden)
SCAN_INTERVAL_MIN   = 30      # Minuten tussen scans
MAX_ANALYSES_BATCH  = 5       # Max AI analyses per cyclus (Pi-vriendelijk)
PRIORITEER_WACHTRIJ = True    # Beste score eerst analyseren

# --- GO / REVIEW / REJECT DREMPELS ---
DREMPEL_GO     = 75   # Totaalscore ≥ 75 → GO    (stuur melding, toon bovenaan)
DREMPEL_REVIEW = 60   # Totaalscore ≥ 60 → REVIEW (manueel bekijken)
#                < 60 → REJECT (automatisch verworpen)

# --- GROQ TOKEN BUDGET (enkel relevant als Groq fallback gebruikt wordt) ---
TOKENS_PER_MINUUT_LIMIET = 6000
TOKENS_PER_DAG_LIMIET    = 450_000
TOKENS_SNELLE_CHECK      = 400
TOKENS_LOCATIE_CHECK     = 600
TOKENS_FOTO_ANALYSE      = 500
TOKENS_VOLLEDIGE_AI      = 1200
TOKENS_JURIDISCH         = 900
DREMPEL_SNELLE_CHECK     = 50
DREMPEL_LOCATIE_CHECK    = 60

# --- IMMOWEB ZOEKFILTERS ---
IMMOWEB_FILTERS = {
    "countries": "BE",
    "orderBy":   "newest",
    "isAPublicSale": "false",
}

# --- LOGGING ---
TOKEN_LOG_BESTAND = "token_gebruik.json"
