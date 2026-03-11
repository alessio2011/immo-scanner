# ============================================================
# IMMO SCANNER - CONFIGURATIE
# Pas deze waarden aan naar uw situatie
# ============================================================

# --- REGIO'S OM TE SCANNEN ---
# Voeg postcodes of gemeentenamen toe
REGIO_POSTCODES = [
    # Voorbeelden - pas aan naar uw voorkeur:
    # "2800",  # Mechelen
    # "2000",  # Antwerpen
    # "9000",  # Gent
]
REGIO_NAMEN = [
    # Voorbeelden:
    # "Mechelen",
    # "Leuven",
]

# --- FINANCIËLE CRITERIA ---
MAX_PRIJS = 500_000          # Maximale aankoopprijs in euro
MIN_PRIJS = 50_000           # Minimale aankoopprijs in euro
MIN_PERCEELOPPERVLAKTE = 200 # Minimale perceelgrootte in m² (voor sloop/herbouw)
MIN_RENDEMENT = 3.5          # Minimaal bruto huurrendement in % (voor verhuur)

# --- TELEGRAM BOT ---
# Stap 1: Stuur een bericht naar @BotFather op Telegram → /newbot → kopieer de token
# Stap 2: Stuur een bericht naar uw bot, ga dan naar:
#          https://api.telegram.org/bot<UW_TOKEN>/getUpdates
#          en kopieer het "id" getal onder "chat"
TELEGRAM_BOT_TOKEN = "UW_BOT_TOKEN_HIER"   # Bv. 123456789:ABCdef...
TELEGRAM_CHAT_ID = "UW_CHAT_ID_HIER"       # Bv. 123456789

# --- GROQ AI API (gratis!) ---
# Aanmaken op: groqcloud.com → inloggen → "API Keys" → "Create API Key"
ANTHROPIC_API_KEY = "UW_GROQ_KEY_HIER"  # Begint met "gsk_..."

# --- SCAN INTERVAL ---
SCAN_INTERVAL_MINUTEN = 30   # Hoe vaak controleren (in minuten)
MAX_PAGINAS = 10             # Hoeveel pagina's per scan (1 pagina = ~30 panden, 10 = ~300)

# --- IMMOWEB ZOEKFILTERS ---
IMMOWEB_FILTERS = {
    "countries": "BE",
    "orderBy": "newest",
    "isAPublicSale": "false",
}
