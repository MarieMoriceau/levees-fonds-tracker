"""
scraper.py — Récupère les levées de fonds depuis Les Pépites Tech
Filtre : >= 3M€, dernier mois
"""

import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

BASE_URL = "https://lespepitestech.com"
SEUIL_M = 3
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; levees-tracker/1.0)"}
SKIP_DOMAINS = {"lespepitestech.com", "eldorado.co", "facebook.com",
                "twitter.com", "linkedin.com", "google.com", "youtube.com"}

STOP_MARKERS = {"prochain article", "article precedent", "voir le site web",
                "show more", "soumis par"}


def get_soup(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                return BeautifulSoup(r.text, "html.parser")
        except Exception:
            time.sleep(2)
    return None


def date_depuis_url(url):
    m = re.search(r"/blog/(\d{4})/(\d{2})/(\d{2})/", url)
    return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def semaine_depuis_url(url):
    m = re.search(r"semaine[- _](\d+)[- _](\d{4})", url, re.IGNORECASE)
    return f"S{m.group(1)}-{m.group(2)}" if m else ""


def extraire_montant(ligne):
    ligne = ligne.strip().replace("\xa0", " ")
    match = re.match(r"^([\d\s,\.]+)\s+en\s+(.+)$", ligne, re.IGNORECASE)
    if not match:
        return None, None
    try:
        raw = match.group(1).strip().replace(",", "").replace(" ", "").replace(".", "")
        tour = match.group(2).strip()
        valeur = float(raw)
        if valeur >= 1_000_000:
            return round(valeur / 1_000_000, 3), tour
        elif valeur >= 1_000:
            return round(valeur / 1_000, 3), tour
        return valeur, tour
    except Exception:
        return None, None


def est_nom_startup(ligne, prochaine):
    if not ligne or len(ligne) < 2:
        return False
    return bool(re.match(r"^[\d\s,\.]+\s+en\s+.+", prochaine or "", re.IGNORECASE))


def est_suspect(montant, tour):
    tour = (tour or "").lower()
    if any(t in tour for t in ["seed", "bridge", "pre-seed", "pre seed", "love money"]) and montant >= 100:
        return True
    if montant >= 800 and "serie" not in tour and "private equity" not in tour:
        return True
    return False


def get_linkedin_from_site(site_url, timeout=6):
    if not site_url or not site_url.startswith("http"):
        return None
    try:
        r = requests.get(site_url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            matches = re.findall(r'linkedin\.com/company/([a-zA-Z0-9\-_\.]+)', r.text)
            if matches:
                slug = matches[0].rstrip('/').split('?')[0].split('"')[0]
                if len(slug) > 1 and not re.match(r'^\d+$', slug):
                    return f"https://www.linkedin.com/company/{slug}"
    except Exception:
        pass
    return None


def guess_linkedin(site_url):
    if not site_url:
        return None
    try:
        domain = urlparse(site_url).netloc.replace("www.", "").split(".")[0]
        if len(domain) > 2:
            return f"https://www.linkedin.com/company/{domain}"
    except Exception:
        pass
    return None


def collecter_urls(jours=35):
    """Collecte les URLs des articles de levées des X derniers jours."""
    date_limite = datetime.now() - timedelta(days=jours)
    urls = []

    for page in range(0, 20):
        page_url = f"{BASE_URL}/blog" + (f"?page={page}" if page > 0 else "")
        soup = get_soup(page_url)
        if not soup:
            break

        links = soup.find_all("a", href=True)
        stop = False
        found = 0

        for link in links:
            href = link["href"]
            if "leves-par-les-startups-francaises" not in href:
                continue
            full_url = (BASE_URL + href) if href.startswith("/") else href
            if full_url in urls:
                continue
            date = date_depuis_url(full_url)
            if date and date >= date_limite:
                urls.append(full_url)
                found += 1
            elif date and date < date_limite:
                stop = True

        if stop or found == 0:
            break
        time.sleep(0.4)

    return list(dict.fromkeys(urls))


def parser_article(url):
    soup = get_soup(url)
    if not soup:
        return []

    date_obj = date_depuis_url(url)
    date_str = date_obj.strftime("%d/%m/%Y") if date_obj else ""
    semaine = semaine_depuis_url(url)

    # Extraction site web depuis le DOM
    site_web_map = {}
    body = soup.find("body")
    current_startup = None
    for tag in body.descendants:
        if not hasattr(tag, "name"):
            continue
        if tag.name == "h2":
            current_startup = tag.get_text(strip=True)
        elif tag.name == "a" and current_startup:
            href = tag.get("href", "")
            if href.startswith("http") and not any(d in href for d in SKIP_DOMAINS):
                if current_startup not in site_web_map:
                    site_web_map[current_startup] = href

    # Parse texte brut
    raw = body.get_text(separator="\n", strip=True)
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    debut = 0
    for i, l in enumerate(lines):
        if re.match(r"^_{3,}$", l):
            debut = i + 1

    resultats = []
    i = debut
    while i < len(lines):
        ligne = lines[i]
        if any(m in ligne.lower() for m in STOP_MARKERS):
            i += 1
            continue

        prochaine = lines[i + 1] if i + 1 < len(lines) else ""
        if est_nom_startup(ligne, prochaine):
            startup = ligne
            montant_m, tour = extraire_montant(prochaine)

            if montant_m and montant_m >= SEUIL_M and not est_suspect(montant_m, tour):
                site = site_web_map.get(startup, "")
                linkedin = get_linkedin_from_site(site) or guess_linkedin(site)

                data = {
                    "startup": startup,
                    "montant": montant_m,
                    "tour": tour,
                    "date": date_str,
                    "date_obj": date_obj.isoformat() if date_obj else "",
                    "semaine": semaine,
                    "description": "",
                    "secteurs": "",
                    "strategie": "",
                    "fondateurs": "",
                    "investisseurs": "",
                    "site_web": site,
                    "linkedin": linkedin or "",
                    "source": url,
                }

                j = i + 2
                while j < len(lines):
                    l = lines[j]
                    lnext = lines[j + 1] if j + 1 < len(lines) else ""
                    if est_nom_startup(l, lnext): break
                    if any(m in l.lower() for m in STOP_MARKERS): break
                    if l in ("Secteurs :", "Secteurs:", "Secteurs"):
                        data["secteurs"] = lnext; j += 2
                    elif l in ("Strategie :", "Stratégie :", "Stratégie:", "Strategie:"):
                        data["strategie"] = lnext; j += 2
                    elif l in ("Fondateurs :", "Fondateurs:", "Fondateurs"):
                        data["fondateurs"] = lnext; j += 2
                    elif l in ("Investisseurs :", "Investisseurs:", "Investisseurs"):
                        data["investisseurs"] = lnext; j += 2
                    elif not data["description"] and len(l) > 30 and not re.match(r"^[\d,\.]", l):
                        data["description"] = l; j += 1
                    else:
                        j += 1

                resultats.append(data)
                i = j
                continue
        i += 1

    return resultats


def scrape_dernier_mois():
    """Point d'entrée principal — retourne les levées du dernier mois."""
    urls = collecter_urls(jours=35)
    levees = []
    for url in urls:
        levees.extend(parser_article(url))
        time.sleep(0.6)

    # Trier par montant décroissant
    levees.sort(key=lambda x: x["montant"], reverse=True)
    return levees
