# 🏠 IMMO SCANNER - SETUP GIDS
## Stap-voor-stap installatie op Raspberry Pi

---

## 📋 WAT HEBT GE NODIG

- Raspberry Pi 4 (met Raspberry Pi OS geïnstalleerd)
- Internetverbinding
- Een telefoon met Telegram (gratis te downloaden)
- Een gratis Groq account (voor de AI)

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

```bash
git clone https://github.com/alessio2011/immo-scanner.git /home/pi/immo-scanner
```

---

## STAP 3 — Telegram Bot aanmaken (gratis, 2 minuten)

### 3a. Telegram installeren
Download Telegram op uw telefoon (gratis in de App Store / Play Store)

### 3b. Bot aanmaken
1. Open Telegram en zoek naar **@BotFather**
2. Stuur het bericht: `/newbot`
3. Geef uw bot een naam (bv. "Immo Scanner")
4. Geef uw bot een gebruikersnaam (moet eindigen op "bot", bv. "immo_scanner_bot")
5. BotFather stuurt u een **token** — kopieer deze! (ziet eruit als `123456789:ABCdef...`)

### 3c. Uw Chat ID vinden
1. Zoek uw bot op in Telegram (op de naam die ge gekozen hebt)
2. Stuur uw bot een willekeurig bericht (bv. "hallo")
3. Ga in uw browser naar:
   `https://api.telegram.org/bot<UW_TOKEN>/getUpdates`
   (vervang `<UW_TOKEN>` door uw echte token)
4. Ge ziet een getal bij `"id"` onder `"chat"` — dat is uw Chat ID

---

## STAP 4 — Groq API Key aanmaken (gratis, geen betaalkaart nodig!)

1. Ga naar **groqcloud.com**
2. Maak een gratis account aan (gewoon email + wachtwoord)
3. Ga naar "API Keys" → "Create API Key"
4. Kopieer de key (begint met `gsk_...`)

> 💡 Groq is volledig gratis: 1.000 analyses per dag.
> Voor de immo scanner is dat ruimschoots genoeg!

---

## STAP 5 — config.py invullen

```bash
cd /home/pi/immo-scanner
nano config.py
```

Vul in:

```python
# Uw regio's (postcodes)
REGIO_POSTCODES = ["2800"]  # bv. Mechelen

# Prijslimieten
MAX_PRIJS = 400_000
MIN_PRIJS = 80_000

# Telegram
TELEGRAM_BOT_TOKEN = "123456789:ABCdef..."  # Uw bot token
TELEGRAM_CHAT_ID = "123456789"              # Uw chat ID

# Groq AI (gratis)
ANTHROPIC_API_KEY = "gsk_..."  # Uw Groq key
```

Opslaan: druk **Ctrl+X** → **Y** → **Enter**

---

## STAP 6 — Testen

```bash
cd /home/pi/immo-scanner
python3 scanner.py
```

Als alles goed is krijgt ge een Telegram bericht: "🚀 Immo Scanner gestart!"

---

## STAP 7 — Automatisch opstarten

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

## 📱 Wat krijgt ge in Telegram?

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
⭐ Prioriteit: 9/10

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

**Geen Telegram bericht:**
→ Controleer uw token en chat ID in config.py
→ Stuur eerst een bericht naar uw bot voor u de scanner start

**Geen panden gevonden:**
→ Verlaag MAX_PRIJS of verwijder postcodes om heel België te scannen

---

*Gemaakt met Claude AI - Anthropic*
