"""
enrich.py — Enrichissement automatique des levées via DuckDuckGo
Appelé depuis watcher.py avant le push Notion
"""
import requests
import re
from bs4 import BeautifulSoup


def ddg_search(query):
    """Recherche DuckDuckGo HTML (sans clé API)."""
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=10,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = [s.get_text(" ", strip=True) for s in soup.select(".result__snippet")]
        return " ".join(snippets[:6])
    except Exception as e:
        print(f"  [enrich] DDG erreur: {e}")
        return ""


def extract_investors(text):
    """Extrait les investisseurs depuis les snippets de recherche."""
    patterns = [
        # "auprès de X, Y et Z, pour..."
        r"auprès de\s+((?:[A-ZÀÂÉÈÊ][A-Za-zÀÂÉÈÊËÎÏÔÙÛÜ\s\-&]+?(?:,\s*|\s+et\s+)?){2,8}?)(?:\.|,\s*pour|\s+pour|\s+afin|\s+pour)",
        # "menée par X avec Y"
        r"(?:levée\s+)?(?:menée|réalisée)\s+par\s+((?:[A-ZÀÂÉÈÊ][A-Za-zÀÂÉÈÊËÎÏÔÙÛÜ\s\-&]+?(?:,\s*|\s+et\s+)?){1,6}?)(?:\.|,|\s+avec|\s+accomp)",
        # "tour de table : X, Y"
        r"tour de table\s+(?:réunit|rassemble|composé de|:)\s*((?:[A-ZÀÂÉÈÊ][A-Za-zÀÂÉÈÊËÎÏÔÙÛÜ\s\-&,]+?){2,8}?)(?:\.|$|\n|\s+pour|\s+afin)",
        # "avec la participation de X, Y"
        r"avec la participation de\s+((?:[A-ZÀÂÉÈÊ][A-Za-zÀÂÉÈÊËÎÏÔÙÛÜ\s\-&]+?(?:,\s*|\s+et\s+)?){2,8}?)(?:\.|,\s*pour|\s+pour)",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            result = m.group(1).strip().rstrip(", ")
            result = re.sub(r'\s+', ' ', result)
            if 10 < len(result) < 300:
                return result
    return ""


def extract_founders(text):
    """Extrait les fondateurs depuis les snippets de recherche."""
    patterns = [
        # "fondée par Prénom Nom, Prénom Nom et Prénom Nom"
        r"[Ff]ond[ée]e?\s+(?:en\s+\d{4}\s+)?par\s+((?:[A-ZÀÂÉÈÊ][a-zàâéèêëîïôùûü\-]+\s+[A-ZÀÂÉÈÊ][a-zàâéèêëîïôùûü\-]+(?:\s*,\s*|\s+et\s+)?){1,4})",
        # "cofondateur Prénom Nom"
        r"[Cc]o(?:\-)?fondateurs?\s+(?:et\s+\w+\s+)?([A-ZÀÂÉÈÊ][a-zàâéèêëîïôùûü\-]+\s+[A-ZÀÂÉÈÊ][a-zàâéèêëîïôùûü\-]+)",
        # "CEO Prénom Nom, co-fondateur"
        r"([A-ZÀÂÉÈÊ][a-zàâéèêëîïôùûü\-]+\s+[A-ZÀÂÉÈÊ][a-zàâéèêëîïôùûü\-]+),?\s+(?:CEO|président|co-fondateur|cofondateur)",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            result = m.group(1).strip().rstrip(", ")
            if 5 < len(result) < 150:
                return result
    return ""


def enrich_levee(levee):
    """
    Enrichit une levée avec fondateurs/investisseurs si manquants.
    Retourne True si au moins un champ a été enrichi.
    """
    startup = levee.get("startup", "")
    montant = levee.get("montant", "")
    annee = "2026"

    needs_founders = not levee.get("fondateurs", "").strip()
    needs_investors = not levee.get("investisseurs", "").strip()

    if not needs_founders and not needs_investors:
        return False  # Déjà complet

    print(f"  [enrich] Enrichissement de {startup}...")
    query = f'"{startup}" levée fonds {montant}M {annee} fondateurs investisseurs French Tech startup'
    text = ddg_search(query)

    if not text:
        print(f"  [enrich] Aucun résultat pour {startup}")
        return False

    enriched = False

    if needs_investors:
        inv = extract_investors(text)
        if inv:
            levee["investisseurs"] = inv
            print(f"  [enrich] ✅ Investisseurs: {inv[:60]}")
            enriched = True

    if needs_founders:
        found = extract_founders(text)
        if found:
            levee["fondateurs"] = found
            print(f"  [enrich] ✅ Fondateurs: {found[:60]}")
            enriched = True

    if not enriched:
        print(f"  [enrich] ⚠️  Extraction vide pour {startup}")

    return enriched
