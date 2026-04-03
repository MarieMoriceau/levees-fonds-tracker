"""
app.py — Dashboard + Watcher automatique
Deux modes :
  - GET /        → Dashboard web (levées du mois)
  - POST /cron   → Déclenché par Render Cron Job (détecte nouveaux articles → Notion)
  - POST /api/refresh → Refresh manuel du dashboard
"""

import json
import os
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, render_template_string, request
from scraper import scrape_dernier_mois
from watcher import run as watcher_run

app = Flask(__name__)

# ── Cache dashboard ───────────────────────────────────────────
_cache = {
    "levees": [],
    "last_update": None,
    "is_loading": False,
}
_lock = threading.Lock()
CACHE_FILE = "cache.json"


def save_cache():
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"levees": _cache["levees"], "last_update": _cache["last_update"]}, f, ensure_ascii=False)
    except Exception:
        pass


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
                _cache["levees"] = data.get("levees", [])
                _cache["last_update"] = data.get("last_update")
        except Exception:
            pass


def refresh_data():
    with _lock:
        if _cache["is_loading"]:
            return
        _cache["is_loading"] = True
    try:
        levees = scrape_dernier_mois()
        with _lock:
            _cache["levees"] = levees
            _cache["last_update"] = datetime.now().strftime("%d/%m/%Y à %H:%M")
            _cache["is_loading"] = False
        save_cache()
        print(f"[refresh] {len(levees)} levées chargées")
    except Exception as e:
        print(f"[refresh] Erreur: {e}")
        with _lock:
            _cache["is_loading"] = False


load_cache()

# ── HTML Dashboard (identique à l'app précédente) ────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Levées de Fonds · French Tech</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0a0a0f;--surface:#13131a;--border:#1e1e2e;--accent:#6ee7b7;
    --accent2:#818cf8;--text:#e2e8f0;--muted:#64748b;
    --seed:#34d399;--serieA:#60a5fa;--serieB:#a78bfa;--serieC:#f472b6;--serieD:#fb923c;--other:#94a3b8;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'Syne',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding-bottom:80px;}
  header{border-bottom:1px solid var(--border);padding:28px 40px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;background:rgba(10,10,15,0.92);backdrop-filter:blur(12px);z-index:100;}
  .logo{font-size:1.1rem;font-weight:800;letter-spacing:-0.02em;}.logo span{color:var(--accent);}
  .header-meta{font-family:'DM Mono',monospace;font-size:0.72rem;color:var(--muted);text-align:right;line-height:1.6;}
  .header-meta strong{color:var(--text);}
  .notion-badge{background:rgba(129,140,248,0.12);border:1px solid rgba(129,140,248,0.3);color:var(--accent2);padding:5px 12px;border-radius:20px;font-family:'DM Mono',monospace;font-size:0.7rem;letter-spacing:0.05em;}
  .btn-refresh{background:var(--accent);color:#0a0a0f;border:none;padding:10px 22px;border-radius:6px;font-family:'Syne',sans-serif;font-weight:700;font-size:0.82rem;cursor:pointer;letter-spacing:0.03em;transition:all .2s;display:flex;align-items:center;gap:8px;}
  .btn-refresh:hover{background:#a7f3d0;transform:translateY(-1px);}
  .btn-refresh:disabled{opacity:.5;cursor:not-allowed;transform:none;}
  .spinner{width:14px;height:14px;border:2px solid #0a0a0f;border-top-color:transparent;border-radius:50%;animation:spin .8s linear infinite;display:none;}
  .btn-refresh.loading .spinner{display:block;}.btn-refresh.loading .btn-text{display:none;}
  @keyframes spin{to{transform:rotate(360deg)}}
  .stats-bar{display:flex;gap:2px;padding:24px 40px;border-bottom:1px solid var(--border);flex-wrap:wrap;}
  .stat-card{background:var(--surface);border:1px solid var(--border);padding:18px 28px;border-radius:8px;flex:1;min-width:160px;}
  .stat-card .val{font-size:2rem;font-weight:800;letter-spacing:-0.04em;color:var(--accent);line-height:1;}
  .stat-card .lbl{font-size:0.72rem;color:var(--muted);margin-top:6px;letter-spacing:0.08em;text-transform:uppercase;font-family:'DM Mono',monospace;}
  .notion-stat{border-color:rgba(129,140,248,0.3);}.notion-stat .val{color:var(--accent2);}
  .filters{padding:20px 40px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--border);}
  .filter-btn{background:transparent;border:1px solid var(--border);color:var(--muted);padding:6px 14px;border-radius:20px;font-family:'DM Mono',monospace;font-size:0.75rem;cursor:pointer;transition:all .15s;}
  .filter-btn:hover,.filter-btn.active{border-color:var(--accent);color:var(--accent);background:rgba(110,231,183,.08);}
  .search-input{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:7px 16px;border-radius:6px;font-family:'DM Mono',monospace;font-size:0.8rem;outline:none;width:220px;margin-left:auto;transition:border-color .15s;}
  .search-input:focus{border-color:var(--accent2);}
  .search-input::placeholder{color:var(--muted);}
  .table-wrap{padding:0 40px;margin-top:8px;overflow-x:auto;}
  table{width:100%;border-collapse:collapse;}
  thead th{font-family:'DM Mono',monospace;font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);padding:14px 16px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap;}
  thead th.sortable{cursor:pointer;user-select:none;}thead th.sortable:hover{color:var(--text);}
  tbody tr{border-bottom:1px solid var(--border);transition:background .12s;}
  tbody tr:hover{background:rgba(255,255,255,.025);}
  tbody td{padding:16px;font-size:.88rem;vertical-align:middle;}
  .startup-name{font-weight:700;font-size:.95rem;letter-spacing:-.01em;}
  .startup-desc{font-size:.72rem;color:var(--muted);margin-top:3px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .montant{font-family:'DM Mono',monospace;font-weight:500;font-size:1rem;color:var(--accent);white-space:nowrap;}
  .tour-badge{display:inline-block;padding:3px 10px;border-radius:4px;font-family:'DM Mono',monospace;font-size:.72rem;font-weight:500;letter-spacing:.04em;white-space:nowrap;}
  .tour-seed{background:rgba(52,211,153,.12);color:var(--seed);}
  .tour-seriea{background:rgba(96,165,250,.12);color:var(--serieA);}
  .tour-serieb{background:rgba(167,139,250,.12);color:var(--serieB);}
  .tour-seriec{background:rgba(244,114,182,.12);color:var(--serieC);}
  .tour-seried{background:rgba(251,146,60,.12);color:var(--serieD);}
  .tour-other{background:rgba(148,163,184,.1);color:var(--other);}
  .secteurs{font-size:.72rem;color:var(--muted);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
  .date-cell{font-family:'DM Mono',monospace;font-size:.78rem;color:var(--muted);white-space:nowrap;}
  .links-cell{display:flex;gap:8px;align-items:center;}
  .link-icon{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:6px;border:1px solid var(--border);color:var(--muted);text-decoration:none;font-size:.75rem;transition:all .15s;}
  .link-icon:hover{border-color:var(--accent);color:var(--accent);background:rgba(110,231,183,.08);}
  .link-icon.li:hover{border-color:var(--accent2);color:var(--accent2);background:rgba(129,140,248,.08);}
  #loading-banner{display:none;background:rgba(110,231,183,.08);border:1px solid rgba(110,231,183,.2);color:var(--accent);padding:12px 40px;font-family:'DM Mono',monospace;font-size:.8rem;text-align:center;letter-spacing:.04em;}
  #loading-banner.visible{display:block;}
  .montant-bar-wrap{display:flex;align-items:center;gap:10px;}
  .montant-bar{height:3px;background:var(--accent);border-radius:2px;opacity:.35;flex-shrink:0;}
  @media(max-width:768px){header,.stats-bar,.filters,.table-wrap{padding-left:16px;padding-right:16px;}.startup-desc,.secteurs{display:none;}}
</style>
</head>
<body>
<header>
  <div class="logo">Levées<span>.</span>fr</div>
  <div class="header-meta">
    <strong id="nb-levees">—</strong> levées ce mois<br>
    Dernière maj: <span id="last-update">—</span>
  </div>
  <div style="display:flex;gap:10px;align-items:center;">
    <span class="notion-badge">⟳ Auto → Notion</span>
    <button class="btn-refresh" id="btn-refresh" onclick="lancerScraping()">
      <div class="spinner"></div><span class="btn-text">⟳ Actualiser</span>
    </button>
  </div>
</header>
<div id="loading-banner">⟳ Scraping en cours… (~2 min). Rafraîchissement automatique.</div>
<div class="stats-bar" id="stats-bar">
  <div class="stat-card"><div class="val" id="stat-total">—</div><div class="lbl">Levées ≥ 3M€</div></div>
  <div class="stat-card"><div class="val" id="stat-volume">—</div><div class="lbl">Volume total (M€)</div></div>
  <div class="stat-card"><div class="val" id="stat-moy">—</div><div class="lbl">Moyenne / deal</div></div>
  <div class="stat-card"><div class="val" id="stat-top">—</div><div class="lbl">Plus gros deal</div></div>
  <div class="stat-card notion-stat"><div class="val" id="stat-notion">—</div><div class="lbl">→ Notion (total)</div></div>
</div>
<div class="filters">
  <button class="filter-btn active" onclick="setFilter('all',this)">Tous</button>
  <button class="filter-btn" onclick="setFilter('Seed',this)">Seed</button>
  <button class="filter-btn" onclick="setFilter('Serie A',this)">Série A</button>
  <button class="filter-btn" onclick="setFilter('Serie B',this)">Série B</button>
  <button class="filter-btn" onclick="setFilter('Serie C',this)">Série C+</button>
  <input class="search-input" type="text" id="search" placeholder="Rechercher…" oninput="renderTable()">
</div>
<div class="table-wrap">
  <table id="main-table">
    <thead><tr>
      <th>Startup</th>
      <th class="sortable" onclick="sortBy('montant')">Montant</th>
      <th>Tour</th>
      <th>Secteurs</th>
      <th class="sortable" onclick="sortBy('date')">Date</th>
      <th>Liens</th>
    </tr></thead>
    <tbody id="table-body"></tbody>
  </table>
</div>
<script>
let allData=[];let currentFilter='all';let currentSort={col:'montant',dir:'desc'};let maxMontant=1;let pollInterval=null;
function tourClass(t){t=(t||'').toLowerCase();if(t.includes('seed'))return'tour-seed';if(t.includes('serie a')||t.includes('série a'))return'tour-seriea';if(t.includes('serie b')||t.includes('série b'))return'tour-serieb';if(t.includes('serie c')||t.includes('série c'))return'tour-seriec';if(t.includes('serie d')||t.includes('serie e')||t.includes('serie f'))return'tour-seried';return'tour-other';}
function setFilter(v,btn){currentFilter=v;document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderTable();}
function sortBy(col){currentSort.col===col?currentSort.dir=currentSort.dir==='asc'?'desc':'asc':null;if(currentSort.col!==col)currentSort={col,dir:'desc'};renderTable();}
function filteredData(){const s=(document.getElementById('search').value||'').toLowerCase();return allData.filter(d=>{const mf=currentFilter==='all'||(currentFilter==='Serie C'?d.tour.toLowerCase().includes('serie c')||d.tour.toLowerCase().includes('serie d')||d.tour.toLowerCase().includes('serie e')||d.tour.toLowerCase().includes('serie f'):d.tour.toLowerCase().includes(currentFilter.toLowerCase()));const ms=!s||d.startup.toLowerCase().includes(s)||(d.secteurs||'').toLowerCase().includes(s)||(d.investisseurs||'').toLowerCase().includes(s);return mf&&ms;});}
function renderTable(){const data=filteredData();data.sort((a,b)=>{let va=currentSort.col==='montant'?a.montant:(a.date_obj||a.date);let vb=currentSort.col==='montant'?b.montant:(b.date_obj||b.date);if(typeof va==='string')va=va.split('/').reverse().join('');if(typeof vb==='string')vb=vb.split('/').reverse().join('');return currentSort.dir==='desc'?(vb>va?1:-1):(va>vb?1:-1);});const tbody=document.getElementById('table-body');if(!data.length){tbody.innerHTML='<tr><td colspan="6" style="text-align:center;padding:60px;color:var(--muted)">Aucun résultat</td></tr>';return;}tbody.innerHTML=data.map(d=>{const bw=Math.max(4,Math.round((d.montant/maxMontant)*80));const si=d.site_web?`<a href="${d.site_web}" target="_blank" class="link-icon" title="Site web">🌐</a>`:'';const li=d.linkedin?`<a href="${d.linkedin}" target="_blank" class="link-icon li" title="LinkedIn">in</a>`:'';return`<tr><td><div class="startup-name">${d.startup}</div><div class="startup-desc">${d.description||d.fondateurs||''}</div></td><td><div class="montant-bar-wrap"><div class="montant">${d.montant.toLocaleString('fr-FR',{maximumFractionDigits:1})} M€</div><div class="montant-bar" style="width:${bw}px"></div></div></td><td><span class="tour-badge ${tourClass(d.tour)}">${d.tour}</span></td><td><div class="secteurs">${d.secteurs||'—'}</div></td><td><div class="date-cell">${d.date}</div></td><td><div class="links-cell">${si}${li}</div></td></tr>`;}).join('');}
function updateStats(data){document.getElementById('stat-total').textContent=data.length;document.getElementById('stat-volume').textContent=data.reduce((s,d)=>s+d.montant,0).toLocaleString('fr-FR',{maximumFractionDigits:0})+' M';document.getElementById('stat-moy').textContent=(data.length?data.reduce((s,d)=>s+d.montant,0)/data.length:0).toLocaleString('fr-FR',{maximumFractionDigits:1})+' M';document.getElementById('stat-top').textContent=(data.length?Math.max(...data.map(d=>d.montant)):0).toLocaleString('fr-FR',{maximumFractionDigits:1})+' M';document.getElementById('nb-levees').textContent=data.length;}
async function loadData(){const r=await fetch('/api/data');const json=await r.json();allData=json.levees||[];maxMontant=allData.length?Math.max(...allData.map(d=>d.montant)):1;document.getElementById('last-update').textContent=json.last_update||'jamais';document.getElementById('stat-notion').textContent=json.notion_total??'—';updateStats(allData);renderTable();if(json.is_loading){showLoading(true);if(!pollInterval)pollInterval=setInterval(pollStatus,4000);}else{showLoading(false);if(pollInterval){clearInterval(pollInterval);pollInterval=null;}}}
async function pollStatus(){const r=await fetch('/api/status');const json=await r.json();if(!json.is_loading){clearInterval(pollInterval);pollInterval=null;await loadData();showLoading(false);}}
function showLoading(v){document.getElementById('loading-banner').classList.toggle('visible',v);const btn=document.getElementById('btn-refresh');btn.classList.toggle('loading',v);btn.disabled=v;}
async function lancerScraping(){showLoading(true);await fetch('/api/refresh',{method:'POST'});pollInterval=setInterval(pollStatus,4000);}
loadData();
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/data")
def api_data():
    # Compter les entrées Notion depuis l'état du watcher
    notion_total = None
    try:
        with open("last_seen.json") as f:
            state = json.load(f)
            last_sync = state.get("last_sync", {})
            notion_total = last_sync.get("ajoutees")
    except Exception:
        pass

    return jsonify({
        "levees": _cache["levees"],
        "last_update": _cache["last_update"],
        "is_loading": _cache["is_loading"],
        "count": len(_cache["levees"]),
        "notion_total": notion_total,
    })


@app.route("/api/status")
def api_status():
    return jsonify({"is_loading": _cache["is_loading"]})


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    t = threading.Thread(target=refresh_data, daemon=True)
    t.start()
    return jsonify({"status": "started"})


@app.route("/cron", methods=["POST"])
def cron_endpoint():
    """
    Appelé par le Render Cron Job toutes les heures.
    Vérifie LPT pour de nouveaux articles → push Notion si nouveau.
    Sécurisé par CRON_SECRET.
    """
    secret = os.environ.get("CRON_SECRET", "")
    if secret and request.headers.get("X-Cron-Secret") != secret:
        return jsonify({"error": "Unauthorized"}), 401

    t = threading.Thread(target=watcher_run, daemon=True)
    t.start()
    return jsonify({"status": "watcher started", "time": datetime.now().isoformat()})


@app.route("/api/watcher-status")
def watcher_status():
    """Retourne l'état du watcher (dernier check, dernière sync)."""
    try:
        with open("last_seen.json") as f:
            state = json.load(f)
        return jsonify({
            "last_check": state.get("last_check"),
            "last_sync": state.get("last_sync"),
            "seen_count": len(state.get("seen_urls", [])),
        })
    except Exception:
        return jsonify({"status": "no state yet"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
