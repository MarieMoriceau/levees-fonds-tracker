"""
watcher.py — Détecte les nouveaux articles de levées LPT et sync vers Notion

Logique :
  1. Vérifie le blog LPT pour tout article "levées" paru depuis la dernière vérif
  2. Si nouvel article → scrape + push Notion
  3. Sauvegarde l'état (dernier article vu) dans last_seen.json

Déclenchement : appelé par Render Cron Job toutes les heures
"""

import json
import os
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from scraper import parser_article, get_soup
from notion_sync import sync_levees

BASE_URL = "https://lespepitestech.com"
STATE_FILE = "last_seen.json"


# ── Gestion de l'état ───────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"seen_urls": [], "last_check": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ── Détection des nouveaux articles ─────────────────────────

def get_latest_levees_urls():
    """Récupère les URLs des articles de levées de la première page du blog."""
    soup = get_soup(f"{BASE_URL}/blog")
    if not soup:
        return []

    urls = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "leves-par-les-startups-francaises" in href:
            full_url = (BASE_URL + href) if href.startswith("/") else href
            if full_url not in urls:
                urls.append(full_url)
    return urls


def find_new_articles(seen_urls):
    """Retourne les URLs d'articles jamais vus."""
    latest = get_latest_levees_urls()
    new = [url for url in latest if url not in seen_urls]
    return new, latest


# ── Point d'entrée principal ─────────────────────────────────

def run():
    print(f"\n{'='*55}")
    print(f"  Watcher LPT → Notion")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"{'='*55}\n")

    state = load_state()
    seen_urls = state.get("seen_urls", [])

    print(f"Articles déjà vus : {len(seen_urls)}")
    print("Vérification du blog LPT...")

    new_articles, all_latest = find_new_articles(seen_urls)

    if not new_articles:
        print("✓ Aucun nouvel article. RAS.\n")
        state["last_check"] = datetime.now().isoformat()
        save_state(state)
        return

    print(f"🔔 {len(new_articles)} nouvel(s) article(s) détecté(s) !\n")

    total_ajoutees = 0
    total_ignorees = 0
    total_erreurs = 0

    for url in new_articles:
        print(f"\n📄 Scraping : {url.split('/')[-1][:60]}")
        levees = parser_article(url)
        print(f"   {len(levees)} levée(s) >= 3M€ trouvée(s)")

        if levees:
            print(f"   Sync vers Notion...")
            aj, ig, err = sync_levees(levees)
            total_ajoutees += aj
            total_ignorees += ig
            total_erreurs += err

        time.sleep(1)

    # Mettre à jour l'état
    # Garder max 200 URLs vues (éviter fichier trop gros)
    updated_seen = list(dict.fromkeys(all_latest + seen_urls))[:200]
    state["seen_urls"] = updated_seen
    state["last_check"] = datetime.now().isoformat()
    state["last_sync"] = {
        "ajoutees": total_ajoutees,
        "ignorees": total_ignorees,
        "erreurs": total_erreurs,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    save_state(state)

    print(f"\n{'='*55}")
    print(f"  ✅ {total_ajoutees} levées ajoutées dans Notion")
    print(f"  ⏭  {total_ignorees} doublons ignorés")
    if total_erreurs:
        print(f"  ❌ {total_erreurs} erreurs")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run()
