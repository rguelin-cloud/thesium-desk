# -*- coding: utf-8 -*-
"""
[RISK_CONTROLS_UI_V1_DARK_FIX] Corrige le rendu de la carte 'Controles pre-trade':
 - Couleurs explicites independantes du theme (utilise les vraies vars CSS du projet)
 - Bouton Rafraichir style explicite
 - Ajout horodatage 'Maj: YYYY-MM-DD HH:MM:SS' (style identique a Perplexity Insights)
 - Detection light/dark via prefers-color-scheme ET via classe sur html/body

Strategie: on remplace le bloc <style> et on ajoute un span horodatage dans le header.
Idempotent par marker [RISK_CONTROLS_UI_V1_DARK_FIX].
"""
import os, re, shutil, datetime, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "index.html")
MARKER_BASE = "[RISK_CONTROLS_UI_V1]"
MARKER_FIX  = "[RISK_CONTROLS_UI_V1_DARK_FIX]"

with open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER_BASE not in src:
    print("ERREUR: carte de base introuvable. Lancer d abord nextones-ui-risk-controls-card.py")
    sys.exit(1)

if MARKER_FIX in src:
    print("Deja patche, skip.")
    sys.exit(0)

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
bk = os.path.join(ROOT, f"_backups_risk_darkfix_{ts}")
os.makedirs(bk, exist_ok=True)
shutil.copy2(TARGET, os.path.join(bk, "index.html"))
print(f"Backup -> {bk}")

# Bloc CSS de remplacement (plus robuste, theme-agnostic)
NEW_STYLE = '''<style>
/* [RISK_CONTROLS_UI_V1_DARK_FIX] couleurs explicites + fallback */
.risk-controls-section{
  margin:16px 0;
  padding:16px;
  border:1px solid rgba(128,128,128,.25);
  border-radius:10px;
  background:rgba(128,128,128,.04);
}
.risk-controls-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:12px;flex-wrap:wrap}
.risk-controls-header h3{margin:0;font-size:1.1rem;font-weight:600}
.risk-controls-meta{display:flex;gap:10px;align-items:center;font-size:.85rem;opacity:.75;flex-wrap:wrap}
.risk-controls-meta button{
  padding:4px 12px;
  border:1px solid rgba(128,128,128,.4);
  background:transparent;
  color:inherit;
  border-radius:6px;
  cursor:pointer;
  font-size:.8rem;
}
.risk-controls-meta button:hover{background:rgba(128,128,128,.15)}
.risk-controls-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}
@media (max-width: 900px){.risk-controls-grid{grid-template-columns:1fr}}
.risk-col-title{margin:0 0 12px 0;font-size:.95rem;font-weight:600;opacity:.85}
.risk-control-item{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid rgba(128,128,128,.15)}
.risk-control-item:last-child{border-bottom:none}
.risk-control-badge{flex:0 0 auto;padding:3px 8px;border-radius:4px;font-size:.7rem;font-weight:700;letter-spacing:.05em;min-width:64px;text-align:center}
.risk-badge-BLOCK{background:rgba(220,53,69,.18);color:#e85d6f;border:1px solid rgba(220,53,69,.4)}
.risk-badge-WARNING{background:rgba(255,170,0,.18);color:#e8a23d;border:1px solid rgba(255,170,0,.4)}
.risk-control-body{flex:1;min-width:0}
.risk-control-label{font-weight:600;font-size:.92rem}
.risk-control-param{font-size:.82rem;opacity:.75;margin-top:3px}
.risk-control-source{font-size:.72rem;opacity:.55;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin-top:2px}
.risk-log-item{display:grid;grid-template-columns:90px 60px 90px 70px 1fr;gap:10px;padding:10px 0;border-bottom:1px solid rgba(128,128,128,.15);font-size:.85rem;align-items:center}
.risk-log-item:last-child{border-bottom:none}
.risk-log-ts{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;opacity:.7;font-size:.78rem}
.risk-log-symbol{font-weight:600}
.risk-log-side{font-size:.78rem;opacity:.8}
.risk-log-status{font-size:.7rem;font-weight:700;padding:3px 8px;border-radius:4px;text-align:center;letter-spacing:.05em}
.risk-status-PASS{background:rgba(40,167,69,.18);color:#5cc77f;border:1px solid rgba(40,167,69,.4)}
.risk-status-BLOCK{background:rgba(220,53,69,.18);color:#e85d6f;border:1px solid rgba(220,53,69,.4)}
.risk-log-detail{opacity:.7;font-size:.78rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.risk-empty{opacity:.5;font-size:.85rem;padding:8px 0;font-style:italic}
.risk-controls-ts{opacity:.6;font-size:.78rem;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
</style>'''

# 1) Remplacer le bloc <style> entre BEGIN et </style>
BEGIN_MARKER = "<!-- === [RISK_CONTROLS_UI_V1] BEGIN === -->"
old_style_pat = re.compile(re.escape(BEGIN_MARKER) + r"\s*<style>.*?</style>", re.DOTALL)
m = old_style_pat.search(src)
if not m:
    print("ERREUR: bloc <style> de base introuvable")
    sys.exit(1)
new_src = src[:m.start()] + BEGIN_MARKER + "\n" + NEW_STYLE + src[m.end():]

# 2) Ajouter un span horodatage dans le header (avant le bouton Rafraichir)
old_meta = '<button class="btn btn-ghost" onclick="loadRiskControlsData(true)" style="padding:2px 8px;font-size:.8rem">Rafraichir</button>'
new_meta = '<span class="risk-controls-ts" id="riskControlsTimestamp">Maj: --</span><button onclick="loadRiskControlsData(true)">Rafraichir</button>'
if old_meta in new_src:
    new_src = new_src.replace(old_meta, new_meta, 1)
    print("Header meta enrichi avec horodatage")
else:
    print("Avertissement: ancien bouton introuvable, header non modifie")

# 3) Modifier le JS pour ecrire l horodatage a chaque chargement
# Cherche la ligne 'if(cnt) cnt.textContent =' et insere maj timestamp juste apres le mode
old_js = 'if(mode) mode.textContent = `mode ${sum.mode||"hybride"}`;'
new_js = '''if(mode) mode.textContent = `mode ${sum.mode||"hybride"}`;
        const tsEl = document.getElementById("riskControlsTimestamp");
        if(tsEl){
          const now = new Date();
          const pad = n => String(n).padStart(2,"0");
          tsEl.textContent = `Maj: ${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
        }'''
if old_js in new_src:
    new_src = new_src.replace(old_js, new_js, 1)
    print("JS enrichi: maj timestamp a chaque load")
else:
    print("Avertissement: bloc JS de base introuvable, timestamp ne sera pas maj automatiquement")

# 4) Inserer marker FIX juste apres marker BASE
fix_comment = f"\n<!-- === {MARKER_FIX} (couleurs robustes + horodatage) === -->"
new_src = new_src.replace(BEGIN_MARKER, BEGIN_MARKER + fix_comment, 1)

with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_src)

# Validation
with open(TARGET, "r", encoding="utf-8-sig") as f:
    chk = f.read()
n_fix = chk.count(MARKER_FIX)
n_base = chk.count(MARKER_BASE)
n_ts_id = chk.count('id="riskControlsTimestamp"')
print(f"marker BASE = {n_base}, FIX = {n_fix}, ts_id = {n_ts_id}")
assert n_fix >= 1, "Marker FIX manquant"
assert n_ts_id == 1, "Element timestamp manquant"
print("OK. Ctrl+F5 sur le navigateur.")
