# ============================================================
# IMMOVATE — GEHEIME SLEUTELS
# !! Zet dit bestand NOOIT op GitHub !!
# !! Staat al in .gitignore !!
# ============================================================

# --- TELEGRAM (admin meldingen) ---
# Stap 1: Maak bot via @BotFather → /newbot
# Stap 2: Stuur /start naar je bot, ga naar:
#         https://api.telegram.org/bot<TOKEN>/getUpdates
#         → zoek "chat":{"id": ...} voor jouw chat ID
TELEGRAM_BOT_TOKEN = "UW_BOT_TOKEN_HIER"    # Bv. 7123456789:AAFabc...
TELEGRAM_ADMIN_ID  = "-100123456789"         # Jouw persoonlijke chat ID (of groeps-ID)

# --- GEMINI AI (gratis, primair) ---
# Ophalen: https://aistudio.google.com → "Get API key" (geen kredietkaart nodig)
GEMINI_API_KEY = "UW_GEMINI_KEY_HIER"       # Begint met "AIza..."

# --- GROQ AI (gratis, fallback als Gemini niet werkt) ---
# Ophalen: https://console.groq.com → "API Keys" → "Create API Key"
# Optioneel — laat leeg als je alleen Gemini gebruikt
GROQ_API_KEY = ""                            # Begint met "gsk_..."
