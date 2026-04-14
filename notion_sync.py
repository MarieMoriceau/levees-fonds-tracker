"""
notion_sync.py — Pousse les levées de fonds dans la base Notion existante
Colonnes de la base : Nom, Date, Description, Fondateurs, Investisseurs,
                      LinkedIn, Montant (M€), Secteurs,
                                            Semaine, Site web, Source, Strategie, Tour
                                            """

import requests
import os
from datetime import datetime

NOTION_VERSION = "2022-06-28"
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")


def notion_headers():
      return {
                "Authorization": f"Bearer {NOTION_TOKEN}",
                "Content-Type": "application/json",
                "Notion-Version": NOTION_VERSION,
      }


def rich_text(content):
      if not content:
                return []
            return [{"text": {"content": str(content)[:2000]}}]


def parse_date(date_str):
      """Convertit DD/MM/YYYY en YYYY-MM-DD pour l'API Notion."""
    if not date_str:
              return None
          for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                                  d = datetime.strptime(date_str.strip(), fmt)
                                  return d.strftime("%Y-%m-%d")
except Exception:
            continue
    return None


def build_secteurs(secteurs_str):
      if not secteurs_str:
                return []
            items = [s.strip() for s in str(secteurs_str).split(",") if s.strip()]
    return [{"name": s[:100]} for s in items[:5]]


def levee_existe(startup, date_str):
      """Verifie si la levee existe deja (anti-doublon)."""
    if not NOTION_TOKEN or not DATABASE_ID:
              return False
          payload = {
                    "filter": {
                                  "property": "Nom",
                                  "title": {"equals": startup}
                    }
          }
    try:
              r = requests.post(
                            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
                            headers=notion_headers(),
                            json=payload,
                            timeout=10,
              )
              if r.status_code == 200:
                            return len(r.json().get("results", [])) > 0
    except Exception as e:
        print(f"  [notion] Erreur verif doublon {startup}: {e}")
    return False


def push_levee(levee):
      """Cree une page dans Notion."""
    if not NOTION_TOKEN or not DATABASE_ID:
              print("  [notion] Variables d'env manquantes")
              return False

    date_notion = parse_date(levee.get("date", ""))

    properties = {
              "Nom": {
                            "title": [{"text": {"content": levee.get("startup", "")[:200]}}]
              },
              "Description": {
                            "rich_text": rich_text(levee.get("description", ""))
              },
              "Fondateurs": {
                            "rich_text": rich_text(levee.get("fondateurs", ""))
              },
              "Investisseurs": {
                            "rich_text": rich_text(levee.get("investisseurs", ""))
              },
              "Semaine": {
                            "rich_text": rich_text(levee.get("semaine", ""))
              },
              "Secteurs": {
                            "multi_select": build_secteurs(levee.get("secteurs", ""))
              },
              "Tour": {
                            "rich_text": rich_text(levee.get("tour", ""))
              },
              "Strategie": {
                            "rich_text": rich_text(levee.get("strategie", ""))
              },
              "Montant (M\u20ac)": {
                            "number": levee.get("montant")
              },
    }

    if date_notion:
              properties["Date"] = {"date": {"start": date_notion}}
              print(f"  [notion] Date: {date_notion} (raw: {levee.get('date', '')})")
else:
        print(f"  [notion] WARN date vide: {levee.get('startup')} raw={levee.get('date', '')}")

    site = levee.get("site_web", "")
    if site and site.startswith("http"):
              properties["Site web"] = {"url": site}

    linkedin = levee.get("linkedin", "")
    if linkedin and linkedin.startswith("http"):
              properties["LinkedIn"] = {"url": linkedin}

    source = levee.get("source", "")
    if source and source.startswith("http"):
              properties["Source"] = {"url": source}

    payload = {
              "parent": {"database_id": DATABASE_ID},
              "properties": properties,
    }

    try:
              r = requests.post(
                            "https://api.notion.com/v1/pages",
                            headers=notion_headers(),
                            json=payload,
                            timeout=15,
              )
              if r.status_code == 200:
                            return True
    else:
            print(f"  [notion] Erreur {r.status_code}: {r.text[:500]}")
                  return False
except Exception as e:
        print(f"  [notion] Exception: {e}")
        return False


def sync_levees(levees):
      """Pousse une liste de levees. Retourne (ajoutees, ignorees, erreurs)."""
    ajoutees = 0
    ignorees = 0
    erreurs = 0

    for levee in levees:
              startup = levee.get("startup", "?")

        if levee_existe(startup, levee.get("date", "")):
                      print(f"  [skip] {startup} deja dans Notion")
                      ignorees += 1
                      continue

        ok = push_levee(levee)
        if ok:
                      print(f"  [ok]   {startup} {levee.get('montant')}M ({levee.get('tour')})")
                      ajoutees += 1
else:
            print(f"  [err]  {startup}")
            erreurs += 1

    return ajoutees, ignorees, erreurs
