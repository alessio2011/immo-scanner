# ============================================================
# IMMO SCANNER - GLOBALE CONFIGURATIE
# Pas deze waarden aan op de Pi
# User-specifieke instellingen worden beheerd via de website
# ============================================================

# --- TELEGRAM BOT (1 bot voor alle users) ---
# Stap 1: Maak bot via @BotFather op Telegram → /newbot
# Stap 2: Elke user stelt hun eigen chat_id in via de website
TELEGRAM_BOT_TOKEN = "UW_BOT_TOKEN_HIER"   # Bv. 123456789:ABCdef...

# --- GEMINI AI (gratis, geen limieten) ---
# Ophalen op: https://aistudio.google.com → Get API key (gratis, geen kredietkaart)
GEMINI_API_KEY = "UW_GEMINI_KEY_HIER"      # Begint met "AIza..."

# --- SCAN INSTELLINGEN ---
MAX_PAGINAS = 10   # Pagina's per postcode per scan (10 = ~300 panden)

# --- IMMOWEB ZOEKFILTERS ---
IMMOWEB_FILTERS = {
    "countries": "BE",
    "orderBy": "newest",
    "isAPublicSale": "false",
}
