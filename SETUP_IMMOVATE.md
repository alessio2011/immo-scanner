# Immovate — Volledige Setup Gids
## Vaste URL van overal bereikbaar, volledig gratis

Na deze gids heb je:
- ✅ `https://immovate.duckdns.org` (of een naam naar keuze)
- ✅ Bereikbaar van overal — thuis, school, gsm, buitenland
- ✅ Raspberry Pi hoeft nooit een publiek IP te hebben
- ✅ Alles start automatisch bij reboot
- ✅ HTTPS inbegrepen (Cloudflare regelt dit)

---

## Overzicht

```
Jij surft naar:   https://immovate.duckdns.org
                           ↓
                  Cloudflare (gratis CDN)
                           ↓  versleutelde tunnel
                  Raspberry Pi thuis (poort 5000)
                           ↓
              Flask serveert website + API
```

De Pi maakt zelf de verbinding naar buiten.
Geen poorten openzetten op je router. Geen publiek IP nodig.

---

## Deel 1 — Gratis domeinnaam halen (5 min)

**1.** Ga naar [https://www.duckdns.org](https://www.duckdns.org)

**2.** Klik "Sign in" → kies Google of GitHub

**3.** Vul bij "sub domain" in: `immovate` (of een andere naam)
   → Je krijgt: `immovate.duckdns.org`

**4.** Klik "add domain"

**5.** Kopieer je **token** (staat bovenaan de pagina na inloggen)
   → Ziet er zo uit: `a1b2c3d4-1234-abcd-5678-ef9012345678`

Bewaar dit token — je hebt het later nodig.

---

## Deel 2 — Cloudflare account aanmaken (3 min)

**1.** Ga naar [https://dash.cloudflare.com](https://dash.cloudflare.com)

**2.** Klik "Sign up" → gratis account aanmaken

**3.** E-mail bevestigen

Je hoeft geen domein toe te voegen in Cloudflare — de tunnel werkt ook zonder.

---

## Deel 3 — Raspberry Pi instellen

### 3a. Project op de Pi zetten

```bash
# Op de Pi (via SSH of direct):
cd /home/pi
git clone https://github.com/alessio2011/immovate.git
cd immovate

# Of als je de zip gebruikt:
unzip immovate.zip -d /home/pi/immovate
cd /home/pi/immovate
```

### 3b. Python packages installeren

```bash
pip3 install flask requests --break-system-packages
```

### 3c. config.py invullen

```bash
nano /home/pi/immovate/config.py
```

Pas aan:
```python
TELEGRAM_BOT_TOKEN = "jouw_bot_token"     # Van @BotFather
TELEGRAM_CHAT_ID   = "-jouw_chat_id"      # Jouw admin chat ID
GEMINI_API_KEY     = "AIza..."            # Van aistudio.google.com
```

### 3d. cloudflared installeren

```bash
# Download voor Raspberry Pi (ARM64)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb \
     -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Controleer installatie
cloudflared --version
```

### 3e. Inloggen bij Cloudflare

```bash
cloudflared tunnel login
```

→ Er verschijnt een link in de terminal, bv:
```
Please open the following URL and log in with your Cloudflare account:
https://dash.cloudflare.com/argotunnel?aud=...
```

Kopieer die link, open in browser, klik "Authorize".

Je ziet dan: `You have successfully logged in.`

### 3f. Tunnel aanmaken

```bash
cloudflared tunnel create immovate
```

Output ziet er zo uit:
```
Created tunnel immovate with id abc123de-f456-7890-abcd-ef1234567890
Tunnel credentials written to /home/pi/.cloudflared/abc123de-...json
```

**Kopieer de tunnel ID** (de lange code na "with id").

### 3g. Config bestand aanmaken

```bash
nano /home/pi/.cloudflared/config.yml
```

Plak dit (vervang `JOUW_TUNNEL_ID` door de echte ID uit stap 3f):

```yaml
tunnel: JOUW_TUNNEL_ID
credentials-file: /home/pi/.cloudflared/JOUW_TUNNEL_ID.json

ingress:
  - hostname: immovate.duckdns.org
    service: http://localhost:5000
  - service: http_status:404
```

Opslaan: `Ctrl+X` → `Y` → `Enter`

### 3h. DuckDNS koppelen aan de tunnel

```bash
cloudflared tunnel route dns immovate immovate.duckdns.org
```

→ Je ziet: `Added CNAME immovate.duckdns.org which will route to...`

---

## Deel 4 — Automatisch starten bij reboot

### 4a. API service

```bash
sudo nano /etc/systemd/system/immovate-api.service
```

Plak:

```ini
[Unit]
Description=Immovate API
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/immovate
ExecStart=/usr/bin/python3 /home/pi/immovate/api.py
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/immovate/api.log
StandardError=append:/home/pi/immovate/api.log

[Install]
WantedBy=multi-user.target
```

### 4b. Scanner service

```bash
sudo nano /etc/systemd/system/immovate-scanner.service
```

Plak:

```ini
[Unit]
Description=Immovate Scanner
After=network.target immovate-api.service

[Service]
User=pi
WorkingDirectory=/home/pi/immovate
ExecStart=/usr/bin/python3 /home/pi/immovate/scanner.py
Restart=always
RestartSec=30
StandardOutput=append:/home/pi/immovate/immo_scanner.log
StandardError=append:/home/pi/immovate/immo_scanner.log

[Install]
WantedBy=multi-user.target
```

### 4c. Cloudflare tunnel service

```bash
sudo cloudflared service install
```

### 4d. Alles activeren en starten

```bash
sudo systemctl daemon-reload
sudo systemctl enable immovate-api immovate-scanner cloudflared
sudo systemctl start immovate-api immovate-scanner cloudflared
```

### 4e. Status controleren

```bash
sudo systemctl status immovate-api
sudo systemctl status immovate-scanner
sudo systemctl status cloudflared
```

Bij alles `Active: active (running)` → ✅ klaar!

---

## Deel 5 — Testen

**1.** Surf naar `https://immovate.duckdns.org`

**2.** Login met:
   - E-mail: `admin@immovate.be`
   - Wachtwoord: `admin123`

**3.** Verander het wachtwoord meteen via Instellingen!

---

## Problemen oplossen

### Website laadt niet

```bash
# Kijk of de API draait
sudo systemctl status immovate-api

# Logs bekijken
tail -f /home/pi/immovate/api.log

# Handmatig testen (poort 5000 lokaal)
curl http://localhost:5000
```

### Tunnel werkt niet

```bash
# Logs van cloudflare
journalctl -u cloudflared -f

# Handmatig testen
cloudflared tunnel run immovate
```

### Na Pi reboot niet bereikbaar

```bash
# Controleer of services starten bij boot
sudo systemctl is-enabled immovate-api
sudo systemctl is-enabled cloudflared

# Opnieuw instellen indien nodig
sudo systemctl enable immovate-api immovate-scanner cloudflared
```

### DuckDNS URL verlopen (zelden)

DuckDNS vraagt elke 30 dagen een ping. Automatiseren:

```bash
# Cron job toevoegen
crontab -e
```

Voeg toe onderaan:
```
*/30 * * * * curl -s "https://www.duckdns.org/update?domains=immovate&token=JOUW_DUCKDNS_TOKEN&ip=" > /dev/null
```

---

## Overzicht eindresultaat

| Wat | Details |
|-----|---------|
| URL | `https://immovate.duckdns.org` |
| HTTPS | Automatisch via Cloudflare |
| Admin login | `admin@immovate.be` / `admin123` |
| Scanner logs | `/home/pi/immovate/immo_scanner.log` |
| API logs | `/home/pi/immovate/api.log` |
| Herstart | Alles start automatisch |
| Kosten | €0 — volledig gratis |

