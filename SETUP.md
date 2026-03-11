# 🏠 IMMO SCANNER - SETUP GIDS
## Stap-voor-stap installatie op Raspberry Pi

---

## 📋 WAT HEBT GE NODIG

- Raspberry Pi 4 (met Raspberry Pi OS geïnstalleerd)
- Internetverbinding
- Een telefoon met WhatsApp
- Een gratis Meta Developer account
- Een gratis Groq account (voor de AI — groqcloud.com)

---

## STAP 1 — Python installeren op de Pi

Open een terminal op uw Pi en typ:

```bash
sudo apt update
sudo apt install python3-pip -y
pip3 install requests
```

---

## STAP 2 — Bestanden op de Pi zetten

Kopieer de volledige `immo-scanner` map naar uw Pi.

U kan dit doen via:
- **USB stick**: kopieer de map en plak ze in `/home/pi/`
- **FileZilla** (gratis programma): verbind met de Pi via SFTP

De map moet zo uitzien op uw Pi:
```
/home/pi/immo-scanner/
    scanner.py
    config.py
    scrapers/
        immoweb.py
    analysis/
        berekeningen.py
        ai_analyse.py
    notifications/
        whatsapp.py
```

---

## STAP 3 — WhatsApp Business API instellen

### 3a. Meta Developer Account aanmaken
1. Ga naar **developers.facebook.com**
2. Maak een gratis account aan (gewoon email + wachtwoord)
3. Klik op "My Apps" → "Create App"
4. Kies "Business" als type
5. Geef uw app een naam (bv. "Immo Scanner")

### 3b. WhatsApp toevoegen
1. In uw app: klik "Add Product" → kies "WhatsApp"
2. Ga naar **WhatsApp → API Setup**
3. U ziet een **Phone Number ID** — kopieer deze
4. U ziet een **Temporary Access Token** — kopieer deze

### 3c. Uw nummer toevoegen
1. Onder "To" → voer uw WhatsApp nummer in (met +32...)
2. Klik "Send test message" om te testen

> ⚠️ **Opmerking**: De gratis versie heeft een tijdelijk token (24u).
> Voor permanent gebruik moet ge een **permanent token** aanmaken via
> Meta Business Manager. Dit is gratis maar vraagt verificatie.
> Zie: business.facebook.com → System Users → Token aanmaken

---

## STAP 4 — Groq API Key aanmaken (gratis, geen betaalkaart nodig!)

1. Ga naar **groqcloud.com**
2. Maak een gratis account aan (gewoon email + wachtwoord)
3. Ga naar "API Keys" → "Create Key"
4. Kopieer de key (begint met `gsk_...`)

> 💡 Groq is volledig gratis: 1.000 analyses per dag.
> Voor de immo scanner is dat ruimschoots genoeg!

---

## STAP 5 — config.py invullen

Open het bestand `config.py` en vul in:

```python
# Uw regio's (postcodes)
REGIO_POSTCODES = ["2800", "2800"]  # bv. Mechelen

# Prijslimieten
MAX_PRIJS = 400_000
MIN_PRIJS = 80_000

# WhatsApp
WHATSAPP_TOKEN = "EAAxxxxxxxx..."      # Uw Meta token
WHATSAPP_PHONE_ID = "1234567890"       # Uw Phone Number ID
WHATSAPP_TO_NUMBER = "32476123456"     # Uw nummer (zonder +)

# Groq AI (gratis)
ANTHROPIC_API_KEY = "gsk_..."  # Uw Groq key
```

---

## STAP 6 — Testen

```bash
cd /home/pi/immo-scanner
python3 scanner.py
```

Als alles goed is krijgt ge een WhatsApp bericht: "🚀 Immo Scanner gestart!"

---

## STAP 7 — Automatisch opstarten (optioneel)

Zodat de scanner automatisch start als de Pi opstart:

```bash
sudo nano /etc/systemd/system/immo-scanner.service
```

Plak dit erin:
```ini
[Unit]
Description=Immo Scanner
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/immo-scanner/scanner.py
WorkingDirectory=/home/pi/immo-scanner
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Dan:
```bash
sudo systemctl enable immo-scanner
sudo systemctl start immo-scanner
```

Nu start de scanner automatisch mee op!

---

## 📱 Wat krijgt ge in WhatsApp?

Voorbeeld bericht:

```
🔥🔥🔥 IMMO ALERT - STERK AAN

📍 Mechelen - 2800
Brusselsesteenweg 145

🏠 Huis | 180m² woning | 650m² perceel
💶 Prijs: €295,000
🛏️ 4 slaapkamers | EPC: F

📊 FINANCIEEL OVERZICHT
💸 Aankoopkost: €330,400
📈 Bruto rendement: 6.2%
🏗️ Projectmarge: 18.5%
🏢 Geschat 8 appartementen mogelijk

🤖 AI BEOORDELING
Groot perceel in centrale locatie met uitstekend 
slooppotentieel. Lage prijs per m² perceel.

💡 Beste strategie: Sloop & herbouw

✅ Kansen:
  • Groot perceel geschikt voor 8 apps
  • Centrale ligging Mechelen
  • Prijs 15% onder marktwaarde

⚠️ Risico's:
  • Hoge EPC vereist renovatie bij verhuur
  • Bouwvergunning onzeker

🔗 https://www.immoweb.be/en/classified/...
```

---

## ❓ PROBLEMEN?

**Scanner start niet:**
→ Controleer of Python 3 geïnstalleerd is: `python3 --version`

**Geen WhatsApp bericht:**
→ Controleer uw token in config.py
→ Test via Meta Developer console

**Geen panden gevonden:**
→ Verlaag MAX_PRIJS of verwijder postcodes om heel België te scannen

---

*Gemaakt met Claude AI - Anthropic*
