"""
Scorekaart — Gewogen subscore systeem
Elke kandidaat krijgt 6 subscores (0-100), gewogen tot een totaalscore.

Drempels (instelbaar in config2.py):
  >= 75 → GO     (automatisch in actieve pipeline)
  >= 60 → REVIEW (menselijke check)
  < 60  → REJECT

Gewichten (som = 1.0):
  Locatie & vraag:        0.25
  Juridisch/bestemming:   0.20
  Financiële haalb.:      0.25
  Bouw/technisch risico:  0.10
  Markt/exit:             0.10
  Strategische fit:       0.10
"""

import logging

logger = logging.getLogger(__name__)

# Gewichten per subscore (som moet 1.0 zijn)
GEWICHTEN = {
    "locatie":    0.25,
    "juridisch":  0.20,
    "financieel": 0.25,
    "technisch":  0.10,
    "markt":      0.10,
    "strategie":  0.10,
}


def score_locatie(pand: dict, locatie_info: dict = None) -> tuple[int, list]:
    """
    Beoordeelt locatiekwaliteit: nabijheid centrum, demografie, connectiviteit.
    """
    score = 50  # Startpunt: onbekend = neutraal
    redenen = []
    gemeente = (pand.get("gemeente", "") or "").lower()
    postcode = str(pand.get("postcode", "") or "")

    # Centrumsteden scoren hoger
    centrumsteden_top = {"antwerpen", "gent", "brussel", "leuven"}
    centrumsteden_mid = {"mechelen", "brugge", "hasselt", "kortrijk", "aalst", "roeselare", "turnhout", "genk"}
    centrumsteden_klein = {"dendermonde", "sint-niklaas", "oostende", "ronse", "ieper", "tongeren"}

    if gemeente in centrumsteden_top:
        score += 35
        redenen.append(f"Topstad: {gemeente} (+35)")
    elif gemeente in centrumsteden_mid:
        score += 20
        redenen.append(f"Centrumstad: {gemeente} (+20)")
    elif gemeente in centrumsteden_klein:
        score += 10
        redenen.append(f"Kleinere centrumstad: {gemeente} (+10)")
    else:
        score -= 5
        redenen.append(f"Landelijke gemeente: {gemeente} (-5)")

    # Locatiedata van Wikipedia/Statbel indien beschikbaar
    if locatie_info:
        bevolking = locatie_info.get("bevolking", 0) or 0
        groei = locatie_info.get("bevolkingsgroei", 0) or 0

        if bevolking > 100_000:
            score += 15
            redenen.append(f"Grote stad >100k inwoners (+15)")
        elif bevolking > 50_000:
            score += 8
            redenen.append(f"Middelgrote stad >50k (+8)")
        elif bevolking > 20_000:
            score += 3
            redenen.append(f"Gemeente >20k (+3)")

        if groei > 1.5:
            score += 10
            redenen.append(f"Sterke bevolkingsgroei (+10)")
        elif groei > 0:
            score += 3
            redenen.append(f"Lichte groei (+3)")
        elif groei < -1:
            score -= 10
            redenen.append(f"Bevolkingskrimp (-10)")

    return max(0, min(100, score)), redenen


def score_juridisch(pand: dict, zachte_vlaggen: list = None) -> tuple[int, list]:
    """
    Beoordeelt juridische haalbaarheid op basis van beschikbare info.
    Zonder echte kadasterdata = inschatting op basis van type en beschrijving.
    """
    score = 60  # Startpunt: basis woonpand zonder bijzonderheden
    redenen = []
    beschrijving = (pand.get("beschrijving", "") or "").lower()
    subtype = (pand.get("subtype", "") or "").lower()
    perceel_opp = pand.get("perceel_opp", 0) or 0

    zachte_vlaggen = zachte_vlaggen or []

    # Pand type bepaalt juridisch uitgangspunt
    if subtype in ["house", "villa", "bungalow", "farmhouse"]:
        score += 20  # Woonbestemming waarschijnlijk
        redenen.append("Woonpand: woonbestemming waarschijnlijk (+20)")
    elif subtype in ["apartment", "flat", "studio"]:
        score += 15
        redenen.append("Appartement: woonbestemming aanwezig (+15)")
    elif subtype in ["land", "building_plot"]:
        score += 25  # Bouwgrond = al bestemming
        redenen.append("Bouwgrond: bouwbestemming aanwezig (+25)")
    elif subtype in ["warehouse", "office", "commercial"]:
        score -= 20  # Herbestemming nodig
        redenen.append("Commercieel/industrieel: herbestemming nodig (-20)")

    # Zachte vlaggen verlagen juridische score
    if "erfpacht_of_opstalrecht" in zachte_vlaggen:
        score -= 15
        redenen.append("Erfpacht/opstalrecht: juridische check nodig (-15)")
    if "asbest_vermeld" in zachte_vlaggen:
        score -= 10
        redenen.append("Asbest vermeld: extra vergunningen/sanering (-10)")

    # Positieve signalen
    if "bouwvergunning" in beschrijving or "vergunning verleend" in beschrijving:
        score += 20
        redenen.append("Bouwvergunning vermeld (+20)")
    if "bouwgrond" in beschrijving or "bouwperceel" in beschrijving:
        score += 15
        redenen.append("Bouwgrond in beschrijving (+15)")

    # Perceel > 300m2 in woonzone = ontwikkelbaar
    if perceel_opp >= 300:
        score += 5
        redenen.append(f"Perceel {perceel_opp}m2 ≥ 300m2 (+5)")

    return max(0, min(100, score)), redenen


def score_financieel(metrics: dict) -> tuple[int, list, dict]:
    """
    Beoordeelt financiële haalbaarheid.
    Geeft ook 3 scenario's terug: pessimistisch/realistisch/optimistisch.
    """
    score = 0
    redenen = []

    project_marge = metrics.get("project_marge", 0)
    bruto_rendement = metrics.get("bruto_rendement", 0)
    netto_rendement = metrics.get("netto_rendement", 0)
    prijs_per_m2 = metrics.get("prijs_per_m2", 0)
    prijs_per_m2_perceel = metrics.get("prijs_per_m2_perceel", 0)
    project_winst = metrics.get("project_winst", 0)
    totale_projectkosten = metrics.get("totale_projectkosten", 0)
    geschatte_verkoopopbrengst = metrics.get("geschatte_verkoopopbrengst", 0)

    # Projectmarge scoring
    if project_marge >= 25:
        score += 40
        redenen.append(f"Uitstekende marge {project_marge}% (+40)")
    elif project_marge >= 15:
        score += 28
        redenen.append(f"Goede marge {project_marge}% (+28)")
    elif project_marge >= 8:
        score += 15
        redenen.append(f"Redelijke marge {project_marge}% (+15)")
    elif project_marge >= 0:
        score += 5
        redenen.append(f"Lage marge {project_marge}% (+5)")
    else:
        score += 0
        redenen.append(f"Negatieve marge {project_marge}% (0)")

    # Huurrendement scoring
    if bruto_rendement >= 7:
        score += 30
        redenen.append(f"Uitstekend rendement {bruto_rendement}% (+30)")
    elif bruto_rendement >= 5:
        score += 20
        redenen.append(f"Goed rendement {bruto_rendement}% (+20)")
    elif bruto_rendement >= 3.5:
        score += 10
        redenen.append(f"Redelijk rendement {bruto_rendement}% (+10)")
    else:
        redenen.append(f"Laag rendement {bruto_rendement}%")

    # Prijs per m2 scoring
    if prijs_per_m2 > 0:
        if prijs_per_m2 < 1000:
            score += 20
            redenen.append(f"Zeer lage prijs/m2: €{prijs_per_m2} (+20)")
        elif prijs_per_m2 < 1500:
            score += 12
            redenen.append(f"Lage prijs/m2: €{prijs_per_m2} (+12)")
        elif prijs_per_m2 < 2000:
            score += 5
            redenen.append(f"Marktconforme prijs/m2: €{prijs_per_m2} (+5)")

    # Perceel prijs scoring
    if prijs_per_m2_perceel > 0:
        if prijs_per_m2_perceel < 200:
            score += 10
            redenen.append(f"Zeer goedkoop perceel €{prijs_per_m2_perceel}/m2 (+10)")
        elif prijs_per_m2_perceel < 400:
            score += 5
            redenen.append(f"Goed perceel €{prijs_per_m2_perceel}/m2 (+5)")
        elif prijs_per_m2_perceel > 1000:
            score -= 10
            redenen.append(f"Duur perceel €{prijs_per_m2_perceel}/m2 (-10)")

    score = max(0, min(100, score))

    # 3 scenario's berekenen (±15% op opbrengst, ±10% op kosten)
    scenarios = {}
    if totale_projectkosten > 0 and geschatte_verkoopopbrengst > 0:
        for naam, opbr_factor, kost_factor in [
            ("pessimistisch", 0.85, 1.10),
            ("realistisch",   1.00, 1.00),
            ("optimistisch",  1.15, 0.95),
        ]:
            opbr = round(geschatte_verkoopopbrengst * opbr_factor)
            kost = round(totale_projectkosten * kost_factor)
            winst = opbr - kost
            marge = round((winst / kost) * 100, 1) if kost > 0 else 0
            scenarios[naam] = {
                "eindwaarde": opbr,
                "totale_kosten": kost,
                "winst": winst,
                "marge_pct": marge,
            }
    elif bruto_rendement > 0:
        # Verhuur scenarios
        prijs = metrics.get("prijs", 0)
        huur = metrics.get("geschatte_huur_maand", 0)
        for naam, huur_f, kost_f in [
            ("pessimistisch", 0.85, 1.10),
            ("realistisch",   1.00, 1.00),
            ("optimistisch",  1.15, 0.95),
        ]:
            j_huur = round(huur * huur_f * 12)
            tot_kost = round(prijs * kost_f * (1 + 0.12))
            rend = round((j_huur / tot_kost) * 100, 1) if tot_kost > 0 else 0
            scenarios[naam] = {
                "jaarhuur": j_huur,
                "totale_kosten": tot_kost,
                "rendement_pct": rend,
            }

    return score, redenen, scenarios


def score_technisch(pand: dict, zachte_vlaggen: list = None) -> tuple[int, list]:
    """
    Beoordeelt technisch/bouwkundig risico.
    Lagere score = meer risico.
    """
    score = 70  # Startpunt: gemiddeld pand
    redenen = []
    zachte_vlaggen = zachte_vlaggen or []
    bouwjaar = pand.get("bouwjaar", 0) or 0
    epc_waarde = pand.get("epc_waarde", 0) or 0
    staat = (pand.get("staat", "") or "").lower()

    # Bouwjaar
    if bouwjaar > 2000:
        score += 20
        redenen.append(f"Recent gebouw ({bouwjaar}) (+20)")
    elif bouwjaar > 1980:
        score += 8
        redenen.append(f"Relatief recent ({bouwjaar}) (+8)")
    elif bouwjaar > 0 and bouwjaar < 1970:
        score -= 15
        redenen.append(f"Oud pand ({bouwjaar}) (-15)")
    if bouwjaar > 0 and bouwjaar < 1950:
        score -= 10
        redenen.append(f"Zeer oud (<1950), asbestrisico (-10)")

    # EPC
    if epc_waarde > 0:
        if epc_waarde < 100:
            score += 15
            redenen.append(f"Uitstekende EPC {epc_waarde} kWh (+15)")
        elif epc_waarde < 300:
            score += 5
            redenen.append(f"Goede EPC {epc_waarde} kWh (+5)")
        elif epc_waarde > 600:
            score -= 15
            redenen.append(f"Slechte EPC {epc_waarde} kWh (-15)")

    # Staat
    if staat in ["good", "as_new"]:
        score += 15
        redenen.append("Goede staat (+15)")
    elif staat in ["to_renovate", "to_be_done_up"]:
        score -= 10
        redenen.append("Renovatie nodig (-10)")

    # Zachte vlaggen
    if "asbest_vermeld" in zachte_vlaggen:
        score -= 20
        redenen.append("Asbest vermeld (-20)")
    if "zeer_slechte_epc" in zachte_vlaggen:
        score -= 10
        redenen.append("Zeer slechte EPC (-10)")

    return max(0, min(100, score)), redenen


def score_markt(pand: dict, metrics: dict) -> tuple[int, list]:
    """
    Beoordeelt marktkansen en exit-mogelijkheden.
    """
    score = 50
    redenen = []
    gemeente = (pand.get("gemeente", "") or "").lower()
    prijs = pand.get("prijs", 0) or 0
    geschat_apps = metrics.get("geschat_aantal_appartementen", 0)

    # Marktvraag per gemeente
    hoge_vraag = {"antwerpen", "gent", "brussel", "leuven", "mechelen"}
    gemiddelde_vraag = {"brugge", "hasselt", "kortrijk", "aalst", "roeselare"}

    if gemeente in hoge_vraag:
        score += 30
        redenen.append(f"Hoge marktvraag in {gemeente} (+30)")
    elif gemeente in gemiddelde_vraag:
        score += 15
        redenen.append(f"Gemiddelde marktvraag in {gemeente} (+15)")

    # Meerdere exit-opties = betere marktpositie
    if geschat_apps >= 4:
        score += 15
        redenen.append(f"{geschat_apps} apps = meerdere kopers mogelijk (+15)")
    elif geschat_apps >= 2:
        score += 8
        redenen.append(f"{geschat_apps} apps = verdeelde exit (+8)")

    # Prijs liquidity: lagere prijs = sneller te verkopen
    if prijs < 200_000:
        score += 10
        redenen.append("Lage prijs = vlot verkoopbaar (+10)")
    elif prijs > 800_000:
        score -= 10
        redenen.append("Hoge prijs = langere verkooptijd (-10)")

    return max(0, min(100, score)), redenen


def score_strategie(pand: dict, metrics: dict) -> tuple[int, list]:
    """
    Beoordeelt strategische fit: type deal, tijdigheid, portefeuillepassing.
    """
    score = 50
    redenen = []
    perceel_opp = pand.get("perceel_opp", 0) or 0
    project_marge = metrics.get("project_marge", 0)
    bruto_rendement = metrics.get("bruto_rendement", 0)
    geschat_apps = metrics.get("geschat_aantal_appartementen", 0)
    renovatie_nodig = metrics.get("renovatie_nodig", False)

    # Beste strategie bepalen
    if geschat_apps >= 3 and project_marge >= 12:
        score += 30
        redenen.append("Ideaal sloop/herbouw project (+30)")
    elif bruto_rendement >= 5 and not renovatie_nodig:
        score += 25
        redenen.append("Klare verhuurinvestering (+25)")
    elif renovatie_nodig and bruto_rendement >= 4:
        score += 15
        redenen.append("Renovatie voor verhuur (+15)")
    elif project_marge >= 8:
        score += 20
        redenen.append("Redelijk ontwikkelingsproject (+20)")

    # Perceel grootte extra punten
    if perceel_opp >= 500:
        score += 15
        redenen.append(f"Groot perceel {perceel_opp}m2 — veel opties (+15)")
    elif perceel_opp >= 300:
        score += 8
        redenen.append(f"Goed perceel {perceel_opp}m2 (+8)")

    return max(0, min(100, score)), redenen


def bereken_totale_score(subscores: dict) -> float:
    """Berekent de gewogen totaalscore uit de subscores."""
    totaal = sum(
        GEWICHTEN[naam] * score
        for naam, score in subscores.items()
        if naam in GEWICHTEN
    )
    return round(totaal, 1)


def bepaal_beslissing(totale_score: float, rode_vlaggen: list,
                      drempel_go: int = 75, drempel_review: int = 60) -> tuple[str, list]:
    """
    Bepaalt GO / REVIEW / REJECT op basis van score en rode vlaggen.
    Geeft (beslissing, acties) terug.
    """
    if rode_vlaggen:
        return "REJECT", ["skip"]

    if totale_score >= drempel_go:
        return "GO", ["contact_agent", "schedule_dd", "biedingsvoorstel"]
    elif totale_score >= drempel_review:
        return "REVIEW", ["human_review", "extra_data_ophalen"]
    else:
        return "REJECT", ["skip"]


def voer_scorekaart_uit(pand: dict, metrics: dict,
                         locatie_info: dict = None,
                         zachte_vlaggen: list = None) -> dict:
    """
    Voert de volledige scorekaart uit en geeft een gestructureerd resultaat.
    Dit is de output die in de Telegram melding en JSON rapport gaat.
    """
    zachte_vlaggen = zachte_vlaggen or []

    s_loc,   r_loc              = score_locatie(pand, locatie_info)
    s_jur,   r_jur              = score_juridisch(pand, zachte_vlaggen)
    s_fin,   r_fin,   scenarios = score_financieel(metrics)
    s_tech,  r_tech             = score_technisch(pand, zachte_vlaggen)
    s_mkt,   r_mkt              = score_markt(pand, metrics)
    s_strat, r_strat            = score_strategie(pand, metrics)

    subscores = {
        "locatie":    s_loc,
        "juridisch":  s_jur,
        "financieel": s_fin,
        "technisch":  s_tech,
        "markt":      s_mkt,
        "strategie":  s_strat,
    }

    totaal = bereken_totale_score(subscores)

    return {
        "subscores":        subscores,
        "totale_score":     totaal,
        "gewichten":        GEWICHTEN,
        "scenarios":        scenarios,
        "score_redenen": {
            "locatie":    r_loc,
            "juridisch":  r_jur,
            "financieel": r_fin,
            "technisch":  r_tech,
            "markt":      r_mkt,
            "strategie":  r_strat,
        },
        "zachte_vlaggen":   zachte_vlaggen,
    }
