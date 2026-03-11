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
MIN_RENDEMENT = 5.0          # Minimaal bruto huurrendement in % (voor verhuur)

# --- WHATSAPP BUSINESS API ---
WHATSAPP_TOKEN = "UW_TOKEN_HIER"          # Meta Business API token
WHATSAPP_PHONE_ID = "UW_PHONE_ID_HIER"   # WhatsApp Business Phone Number ID
WHATSAPP_TO_NUMBER = "32XXXXXXXXX"        # Uw nummer (zonder + maar met landcode, bv. 32476...)

# --- GROQ AI API (gratis!) ---
# Aanmaken op: groqcloud.com → inloggen → "API Keys" → "Create API Key"
ANTHROPIC_API_KEY = "UW_GROQ_KEY_HIER"  # Begint met "gsk_..."

# --- SCAN INTERVAL ---
SCAN_INTERVAL_MINUTEN = 30   # Hoe vaak controleren (in minuten)

# --- IMMOWEB ZOEKFILTERS ---
IMMOWEB_FILTERS = {
    "countries": "BE",
    "orderBy": "newest",
    "isAPublicSale": "false",
}
