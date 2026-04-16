"""
notion_sync.py — types exacts vérifiés via API Notion :
Secteurs=rich_text, Strategie=multi_select, pas de Ajouté le
"""
import requests, os
from datetime import datetime

NOTION_VERSION = "2022-06-28"
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

def notion_headers():
    return {"Authorization": f"Bearer {NOTION_TOKEN}", "Content-Type": "application/json", "Notion-Version": NOTION_VERSION}

def rich_text(v):
    return [{"text": {"content": str(v)[:2000]}}] if v else []

def parse_date(s):
    if not s: return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try: return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except: pass
    return None

def levee_existe(startup):
    if not NOTION_TOKEN or not DATABASE_ID: return False
    try:
        r = requests.post(f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=notion_headers(), json={"filter": {"property": "Nom", "title": {"equals": startup}}}, timeout=10)
        return len(r.json().get("results", [])) > 0 if r.status_code == 200 else False
    except: return False

def push_levee(levee):
    if not NOTION_TOKEN or not DATABASE_ID:
        print("  [notion] Variables manquantes"); return False
    date = parse_date(levee.get("date", ""))
    props = {
        "Nom":          {"title": [{"text": {"content": levee.get("startup","")[:200]}}]},
        "Description":  {"rich_text": rich_text(levee.get("description",""))},
        "Fondateurs":   {"rich_text": rich_text(levee.get("fondateurs",""))},
        "Investisseurs":{"rich_text": rich_text(levee.get("investisseurs",""))},
        "Semaine":      {"rich_text": rich_text(levee.get("semaine",""))},
        "Secteurs":     {"rich_text": rich_text(levee.get("secteurs",""))},
        "Tour":         {"rich_text": rich_text(levee.get("tour",""))},
        "Strategie":    {"multi_select": [{"name": s.strip()[:100]} for s in str(levee.get("strategie","")).split(",") if s.strip()]},
        "Montant (M€)": {"number": levee.get("montant")},
    }
    if date: props["Date"] = {"date": {"start": date}}
    for field, key in [("Site web","site_web"),("LinkedIn","linkedin"),("Source","source")]:
        v = levee.get(key,"")
        if v and v.startswith("http"): props[field] = {"url": v}
    try:
        r = requests.post("https://api.notion.com/v1/pages",
            headers=notion_headers(), json={"parent": {"database_id": DATABASE_ID}, "properties": props}, timeout=15)
        if r.status_code == 200: return True
        print(f"  [erreur] {r.status_code}: {r.json().get('message','')[:200]}")
        return False
    except Exception as e:
        print(f"  [exception] {e}"); return False

def sync_levees(levees):
    ok = skip = err = 0
    for l in levees:
        nom = l.get("startup","?")
        if levee_existe(nom):
            print(f"  [skip] {nom}"); skip += 1
        elif push_levee(l):
            print(f"  [ok] {nom} {l.get('montant')}M€"); ok += 1
        else:
            print(f"  [err] {nom}"); err += 1
    return ok, skip, err
