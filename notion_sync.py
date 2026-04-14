"""
notion_sync.py — Pousse les levees de fonds dans la base Notion
Types reels de la base:
  Nom=title, Date=date, Description=rich_text, Fondateurs=rich_text,
    Investisseurs=rich_text, LinkedIn=url, Montant(M€)=number,
      Secteurs=rich_text, Semaine=rich_text, Site web=url,
        Source=url, Strategie=multi_select, Tour=rich_text
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
      if not date_str:
                return None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                      try:
                                    return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
except Exception:
            continue
    return None


def levee_existe(startup):
      if not NOTION_TOKEN or not DATABASE_ID:
                return False
            try:
                      r = requests.post(
                                    f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
                                    headers=notion_headers(),
                                    json={"filter": {"property": "Nom", "title": {"equals": startup}}},
                                    timeout=10,
                      )
                      if r.status_code == 200:
                                    return len(r.json().get("results", [])) > 0
            except Exception as e:
                      print(f"  [notion] Erreur doublon {startup}: {e}")
                  return False


def push_levee(levee):
      if not NOTION_TOKEN or not DATABASE_ID:
                print("  [notion] Variables manquantes")
                return False

    date_notion = parse_date(levee.get("date", ""))
    strategie_val = levee.get("strategie", "")
    strategie_ms = [{"name": strategie_val[:100]}] if strategie_val else []

    properties = {
              "Nom":               {"title": [{"text": {"content": levee.get("startup", "")[:200]}}]},
              "Description":       {"rich_text": rich_text(levee.get("description", ""))},
              "Fondateurs":        {"rich_text": rich_text(levee.get("fondateurs", ""))},
              "Investisseurs":     {"rich_text": rich_text(levee.get("investisseurs", ""))},
              "Semaine":           {"rich_text": rich_text(levee.get("semaine", ""))},
              "Tour":              {"rich_text": rich_text(levee.get("tour", ""))},
              "Secteurs":          {"rich_text": rich_text(levee.get("secteurs", ""))},
              "Strategie":         {"multi_select": strategie_ms},
              "Montant (M\u20ac)": {"number": levee.get("montant")},
    }

    if date_notion:
              properties["Date"] = {"date": {"start": date_notion}}
else:
        print(f"  [warn] date vide: {levee.get('startup')} raw={levee.get('date')}")

    site = levee.get("site_web", "")
    if site and site.startswith("http"):
              properties["Site web"] = {"url": site}
          linkedin = levee.get("linkedin", "")
    if linkedin and linkedin.startswith("http"):
              properties["LinkedIn"] = {"url": linkedin}
          source = levee.get("source", "")
    if source and source.startswith("http"):
              properties["Source"] = {"url": source}

    try:
              r = requests.post(
                            "https://api.notion.com/v1/pages",
                            headers=notion_headers(),
                            json={"parent": {"database_id": DATABASE_ID}, "properties": properties},
                            timeout=15,
              )
              if r.status_code == 200:
                            return True
                        print(f"  [notion] Erreur {r.status_code}: {r.text[:300]}")
        return False
except Exception as e:
        print(f"  [notion] Exception: {e}")
        return False


def sync_levees(levees):
      ajoutees = ignorees = erreurs = 0
    for levee in levees:
              startup = levee.get("startup", "?")
        if levee_existe(startup):
                      print(f"  [skip] {startup}")
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
