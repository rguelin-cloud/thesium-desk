# -*- coding: utf-8 -*-
# [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1]
# Patches UI :
#   A) index.html : skeleton 5 kpi-card au lieu de 4
#   B) index.html : SUPPRIME le tableau PIVA (L1043-1063 + L2421-2447)
#   C) index.html : ajoute modal capital flow
#   D) app.js     : renderKPIs() injecte 5 cards : Portfolio Value | Unrealized P&L | Total Return | Cash | Daily P&L
#   E) app.js     : SUPPRIME le call renderPortfolioIdeal() L1016 et la fonction L1431-1556
#   F) app.js     : ajoute openCapitalFlowModal() + submitCapitalFlow() + loadCapitalFlows()
#   G) index.html : bouton "Enregistrer flux" dans le header de la section Positions
#
# Idempotent : skip si marker [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] present.

import re
import shutil
import time
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = BASE / "index.html"
JS = BASE / "app.js"
MARKER = "FIX_UI_PNL_2FIELDS_AND_FLOWS_V1"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, text):
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))

html = read_text(HTML)
js = read_text(JS)

if MARKER in html and MARKER in js:
    print(f"[SKIP] marker {MARKER} deja present dans les 2 fichiers")
    raise SystemExit(0)

ts = time.strftime("%Y%m%d_%H%M%S")
shutil.copy2(HTML, HTML.with_suffix(f".html.bak.{ts}"))
shutil.copy2(JS, JS.with_suffix(f".js.bak.{ts}"))
print(f"[OK] backups html/js -> .bak.{ts}")

# ============================================================
# A) HTML : skeleton 5 cards
# ============================================================
old_skel = (
    '<div class="kpi-grid" id="kpiGrid">\n'
    '        <!-- Skeleton loaders -->\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '      </div>'
)
new_skel = (
    '<div class="kpi-grid" id="kpiGrid">\n'
    '        <!-- Skeleton loaders [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] 5 cards -->\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '        <div class="kpi-card"><div class="skeleton skeleton-card"></div></div>\n'
    '      </div>'
)
if old_skel in html:
    html = html.replace(old_skel, new_skel, 1)
    print("[OK] HTML skeleton -> 5 cards")
else:
    print("[WARN] skeleton 4-cards non trouve (peut-etre deja 5)")

# ============================================================
# B) HTML : supprimer PIVA section (L1043-1063 environ)
# Recherche du bloc <div class="table-section" id="portfolioIdealSection" ... > ... </div>
# Strategie : on enleve depuis "<!-- Portfolio Ideal" (commentaire si present) jusqu'a la balise de fermeture de cette table-section.
# Comme le HTML est touffu, on opere via regex sur l'attribut id="portfolioIdealSection".
# ============================================================
# Regex pour matcher l'ouverture div table-section id=portfolioIdealSection
piva_open_rgx = re.compile(
    r'(<!--[^>]*Portfolio[^>]*Id[e\u00e9]al[^>]*-->\s*)?'  # commentaire optionnel
    r'<div\s+class="table-section"\s+id="portfolioIdealSection"[^>]*>',
    re.IGNORECASE,
)
m = piva_open_rgx.search(html)
if m:
    start = m.start()
    # Compter <div> et </div> pour trouver le </div> matching
    pos = m.end()
    depth = 1
    while depth > 0 and pos < len(html):
        nxt_open = html.find("<div", pos)
        nxt_close = html.find("</div>", pos)
        if nxt_close == -1:
            print("[ERR] PIVA : fermeture </div> introuvable")
            raise SystemExit(2)
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            pos = nxt_open + 4
        else:
            depth -= 1
            pos = nxt_close + 6
    # Inclure aussi un \n eventuel apres
    end = pos
    while end < len(html) and html[end] in (" ", "\t"):
        end += 1
    if end < len(html) and html[end] == "\n":
        end += 1
    removed = html[start:end]
    html = html[:start] + f"<!-- [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] PIVA removed ({len(removed)} chars) -->\n" + html[end:]
    print(f"[OK] PIVA section #1 supprimee ({len(removed)} chars)")
else:
    print("[WARN] PIVA #portfolioIdealSection deja absente")

# Second bloc PIVA "Portfolio ideal vs actuel" (L2421-2447 si present)
piva2_rgx = re.compile(
    r'<h2[^>]*>\s*Portfolio\s+id[e\u00e9]al\s+vs\s+actuel\s*</h2>',
    re.IGNORECASE,
)
m2 = piva2_rgx.search(html)
if m2:
    # On remonte au plus proche <div ...> contenant et on coupe jusqu'a son </div> matching.
    # Heuristique : trouver le <div ouvrant juste avant le h2 (max 500 chars en arriere).
    region_start = max(0, m2.start() - 800)
    open_idx = html.rfind("<div", region_start, m2.start())
    if open_idx == -1:
        print("[WARN] PIVA #2 : conteneur ouvrant non trouve, skip")
    else:
        # Match </div> de ce <div
        pos = open_idx + 4
        depth = 1
        while depth > 0 and pos < len(html):
            nxt_open = html.find("<div", pos)
            nxt_close = html.find("</div>", pos)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                pos = nxt_open + 4
            else:
                depth -= 1
                pos = nxt_close + 6
        if depth == 0:
            removed2 = html[open_idx:pos]
            html = html[:open_idx] + f"<!-- [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] PIVA#2 removed -->\n" + html[pos:]
            print(f"[OK] PIVA section #2 (h2 Portfolio ideal vs actuel) supprimee ({len(removed2)} chars)")
else:
    print("[INFO] PIVA #2 (h2 Portfolio ideal vs actuel) absente")

# ============================================================
# C) HTML : ajouter le modal capital-flow + bouton dans header section Positions
# Bouton inserer dans le header de la section Positions, a cote du bouton Modifier.
# Cible : <span class="section-title">Positions</span> ... <button ... portfolioEditBtn ...>
# On insere notre bouton AVANT portfolioEditBtn.
# ============================================================
edit_btn_anchor = '<button class="btn btn-ghost" id="portfolioEditBtn"'
flow_btn = (
    '<button class="btn btn-ghost" id="capitalFlowBtn" onclick="openCapitalFlowModal()" '
    'title="Enregistrer un depot ou retrait" '
    'style="font-size:var(--text-xs);padding:2px 8px;border:1px solid var(--color-border);'
    'border-radius:var(--radius-sm);cursor:pointer;color:var(--color-text-muted);margin-right:6px">'
    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" style="vertical-align:middle;margin-right:2px">'
    '<path d="M12 5v14"/><path d="M5 12h14"/></svg>'
    'Flux'
    '</button>\n              '
)
if 'id="capitalFlowBtn"' in html:
    print("[SKIP] bouton capitalFlowBtn deja present")
else:
    if edit_btn_anchor in html:
        html = html.replace(edit_btn_anchor, flow_btn + edit_btn_anchor, 1)
        print("[OK] bouton 'Flux' ajoute avant portfolioEditBtn")
    else:
        print("[WARN] anchor portfolioEditBtn introuvable, bouton non insere")

# Modal HTML : insere juste avant </body>
modal_html = '''
<!-- [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] Capital Flow Modal -->
<div id="capitalFlowModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center" onclick="if(event.target===this)closeCapitalFlowModal()">
  <div style="background:var(--color-surface,#1a1a1a);color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:24px;width:420px;max-width:90vw;box-shadow:0 10px 40px rgba(0,0,0,0.5)">
    <h3 style="margin:0 0 16px 0;font-size:var(--text-lg);font-weight:600">Enregistrer un flux de capital</h3>
    <div style="display:flex;flex-direction:column;gap:12px">
      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">
        Type
        <select id="cfSide" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm)">
          <option value="deposit">Depot (+)</option>
          <option value="withdrawal">Retrait (-)</option>
        </select>
      </label>
      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">
        Montant (USD)
        <input type="number" id="cfAmount" step="0.01" min="0" placeholder="ex: 10000" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm);font-family:var(--font-mono)" />
      </label>
      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">
        Date
        <input type="date" id="cfDate" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm);font-family:var(--font-mono)" />
      </label>
      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">
        Note (optionnel)
        <input type="text" id="cfNote" placeholder="ex: virement broker" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm)" />
      </label>
      <div id="cfFlowsList" style="margin-top:8px;max-height:140px;overflow-y:auto;border:1px solid var(--color-divider);border-radius:var(--radius-sm);padding:8px;font-size:var(--text-xs);font-family:var(--font-mono);color:var(--color-text-muted);background:var(--color-surface-alt,rgba(255,255,255,0.02))"></div>
    </div>
    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:20px">
      <button onclick="closeCapitalFlowModal()" style="padding:6px 14px;border:1px solid var(--color-border);border-radius:var(--radius-sm);background:transparent;color:var(--color-text-muted);cursor:pointer;font-size:var(--text-sm)">Annuler</button>
      <button onclick="submitCapitalFlow()" style="padding:6px 14px;border:1px solid var(--color-accent,#3b82f6);border-radius:var(--radius-sm);background:var(--color-accent,#3b82f6);color:#fff;cursor:pointer;font-size:var(--text-sm);font-weight:500">Enregistrer</button>
    </div>
  </div>
</div>
'''
if 'id="capitalFlowModal"' in html:
    print("[SKIP] capitalFlowModal deja present")
else:
    body_close = html.rfind("</body>")
    if body_close == -1:
        print("[ERR] </body> introuvable")
        raise SystemExit(3)
    html = html[:body_close] + modal_html + "\n" + html[body_close:]
    print("[OK] capitalFlowModal injecte avant </body>")

# ============================================================
# D) JS : renderKPIs() -> 5 cards
# Remplace le bloc kpiGrid.innerHTML = `...4 cards...` par 5 cards.
# ============================================================
# Localise le innerHTML actuel (du <div class="kpi-card"> "Portfolio Value" jusqu'au dernier "Daily P&L" card).
old_kpi_block_rgx = re.compile(
    r'(kpiGrid\.innerHTML\s*=\s*`)([\s\S]*?Daily P&amp;L[\s\S]*?</div>\s*</div>)(\s*`;)',
    re.MULTILINE,
)
m_kpi = old_kpi_block_rgx.search(js)
if not m_kpi:
    print("[ERR] bloc renderKPIs innerHTML introuvable")
    raise SystemExit(4)

new_kpi_block = '''
    <div class="kpi-card">
      <div class="kpi-label">Portfolio Value</div>
      <div class="kpi-value mono">${fmtUSDCompact(pv)}</div>
      <div class="kpi-delta neutral">AUM</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Unrealized P&amp;L</div>
      <div class="kpi-value mono ${colorClass(unrealizedPnl)}">${fmtUSD(unrealizedPnl)}</div>
      <div class="kpi-delta ${unrealizedPnlPct > 0 ? 'positive' : unrealizedPnlPct < 0 ? 'negative' : 'neutral'}">
        ${unrealizedPnlPct > 0 ? '\\u25B2' : unrealizedPnlPct < 0 ? '\\u25BC' : ''}
        ${fmtPct(unrealizedPnlPct)}
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Total Return</div>
      <div class="kpi-value mono ${colorClass(totalReturn)}">${fmtUSD(totalReturn)}</div>
      <div class="kpi-delta ${totalReturnPct > 0 ? 'positive' : totalReturnPct < 0 ? 'negative' : 'neutral'}">
        ${totalReturnPct > 0 ? '\\u25B2' : totalReturnPct < 0 ? '\\u25BC' : ''}
        ${fmtPct(totalReturnPct)}
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Cash Available</div>
      <div class="kpi-value mono">${fmtUSDCompact(cash)}</div>
      <div class="kpi-delta neutral">
        ${cash != null && pv != null ? fmtPct((cash / pv) * 100) + ' of NAV' : ''}
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Daily P&amp;L</div>
      <div class="kpi-value mono ${colorClass(pnl)}">${fmtUSD(pnl)}</div>
      <div class="kpi-delta ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral'}">
        ${pnl > 0 ? '\\u25B2' : pnl < 0 ? '\\u25BC' : ''}
        ${pnl != null && pv != null ? fmtPct((pnl / pv) * 100) : ''}
      </div>
    </div>
  '''

js = js[:m_kpi.start()] + 'kpiGrid.innerHTML = `' + new_kpi_block + '`;' + js[m_kpi.end():]
print("[OK] renderKPIs -> 5 cards (Portfolio Value | Unrealized P&L | Total Return | Cash | Daily P&L)")

# Maintenant ajouter les const en haut de renderKPIs (apres const totalPnl/totalPnlPct).
# On trouve la ligne "const totalPnlPct = p.total_pnl_pct ??"
const_anchor = "const totalPnlPct = p.total_pnl_pct"
m_const = js.find(const_anchor)
if m_const == -1:
    print("[ERR] anchor const totalPnlPct introuvable")
    raise SystemExit(5)
# Trouve fin de cette ligne
eol = js.find("\n", m_const)
new_consts = (
    "\n  // [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] 2 champs : unrealized + total_return\n"
    "  const unrealizedPnl = p.unrealized_pnl ?? totalPnl;\n"
    "  const unrealizedPnlPct = p.unrealized_pnl_pct ?? totalPnlPct;\n"
    "  const totalReturn = p.total_return ?? p.total_pnl ?? null;\n"
    "  const totalReturnPct = p.total_return_pct ?? p.total_pnl_pct ?? null;"
)
js = js[:eol] + new_consts + js[eol:]
print("[OK] constantes unrealized*/totalReturn* ajoutees")

# ============================================================
# E) JS : neutraliser renderPortfolioIdeal call + function
# - Trouver l'appel renderPortfolioIdeal(); et le commenter
# - Trouver function renderPortfolioIdeal(...) { ... } et l'envelopper en commentaire
# ============================================================
call_rgx = re.compile(r"^(\s*)renderPortfolioIdeal\s*\(\s*\)\s*;", re.MULTILINE)
nb = 0
def _comment_call(m):
    global nb
    nb += 1
    return m.group(1) + "// [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] PIVA removed -- " + m.group(0).strip()
js = call_rgx.sub(_comment_call, js)
print(f"[OK] {nb} call(s) renderPortfolioIdeal() commentes")

# Function definition
func_rgx = re.compile(r"function\s+renderPortfolioIdeal\s*\(")
fm = func_rgx.search(js)
if fm:
    # Trouve l'accolade ouvrante { puis matche jusqu'a la fermante au meme niveau
    brace_open = js.find("{", fm.end())
    if brace_open == -1:
        print("[WARN] { de renderPortfolioIdeal introuvable")
    else:
        depth = 1
        i = brace_open + 1
        in_str = None
        while i < len(js) and depth > 0:
            c = js[i]
            if in_str:
                if c == "\\":
                    i += 2
                    continue
                if c == in_str:
                    in_str = None
            else:
                if c in ('"', "'", "`"):
                    in_str = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
            i += 1
        if depth == 0:
            # Wrap la fonction en commentaire block
            func_start = fm.start()
            func_end = i  # juste apres la }
            replacement = (
                "/* [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] renderPortfolioIdeal removed (PIVA dropped)\n"
                + js[func_start:func_end] +
                "\n*/\n"
            )
            js = js[:func_start] + replacement + js[func_end:]
            print("[OK] function renderPortfolioIdeal commentee")
        else:
            print("[WARN] balance accolades echouee pour renderPortfolioIdeal")
else:
    print("[INFO] function renderPortfolioIdeal absente (deja supprimee?)")

# ============================================================
# F) JS : ajouter les helpers capital flow (openCapitalFlowModal, submitCapitalFlow, etc.)
# Insere a la fin du fichier (apres le dernier }).
# ============================================================
capital_flow_js = '''

// [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1] Capital Flow helpers
function openCapitalFlowModal() {
  const modal = document.getElementById('capitalFlowModal');
  if (!modal) return;
  modal.style.display = 'flex';
  // Date par defaut = aujourd'hui
  const today = new Date().toISOString().slice(0, 10);
  const dateInput = document.getElementById('cfDate');
  if (dateInput && !dateInput.value) dateInput.value = today;
  // Reset
  document.getElementById('cfAmount').value = '';
  document.getElementById('cfNote').value = '';
  // Charge la liste existante
  loadCapitalFlowsList();
}

function closeCapitalFlowModal() {
  const modal = document.getElementById('capitalFlowModal');
  if (modal) modal.style.display = 'none';
}

async function loadCapitalFlowsList() {
  const container = document.getElementById('cfFlowsList');
  if (!container) return;
  container.innerHTML = '<span style="color:var(--color-text-faint)">Chargement...</span>';
  try {
    const res = await (typeof apiFetch === 'function'
      ? apiFetch('/api/portfolio/capital-flows')
      : fetch('/api/portfolio/capital-flows'));
    const data = await res.json();
    const flows = data.flows || [];
    if (flows.length === 0) {
      container.innerHTML = '<span style="color:var(--color-text-faint)">Aucun flux enregistre</span>';
      return;
    }
    const net = data.net_capital_flows || 0;
    let html = '<div style="margin-bottom:6px;font-weight:600;color:var(--color-text)">Net cumule : ' +
      (net >= 0 ? '+' : '') + net.toLocaleString('en-US', {maximumFractionDigits:2}) + ' USD</div>';
    flows.forEach(f => {
      const sign = f.side === 'deposit' ? '+' : '-';
      const color = f.side === 'deposit' ? '#22c55e' : '#ef4444';
      html += '<div style="display:flex;justify-content:space-between;padding:2px 0">' +
        '<span>' + f.date + ' <span style="color:' + color + '">' + sign +
        f.amount.toLocaleString('en-US', {maximumFractionDigits:2}) + '</span>' +
        (f.note ? ' <span style="color:var(--color-text-faint)">(' + f.note + ')</span>' : '') +
        '</span>' +
        '<button onclick="deleteCapitalFlow(' + f.id + ')" title="Supprimer" ' +
        'style="background:none;border:none;color:var(--color-text-faint);cursor:pointer;font-size:11px;padding:0 4px">x</button>' +
        '</div>';
    });
    container.innerHTML = html;
  } catch (e) {
    container.innerHTML = '<span style="color:#ef4444">Erreur : ' + e.message + '</span>';
  }
}

async function submitCapitalFlow() {
  const side = document.getElementById('cfSide').value;
  const amount = parseFloat(document.getElementById('cfAmount').value);
  const date = document.getElementById('cfDate').value;
  const note = document.getElementById('cfNote').value;
  if (!amount || amount <= 0) {
    alert('Montant invalide');
    return;
  }
  try {
    const res = await (typeof apiFetch === 'function'
      ? apiFetch('/api/portfolio/capital-flow', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({amount, side, date, note}),
        })
      : fetch('/api/portfolio/capital-flow', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({amount, side, date, note}),
        }));
    if (!res.ok) {
      const err = await res.json().catch(() => ({detail: res.statusText}));
      alert('Erreur : ' + (err.detail || res.status));
      return;
    }
    // Reload list + dashboard
    await loadCapitalFlowsList();
    document.getElementById('cfAmount').value = '';
    document.getElementById('cfNote').value = '';
    if (typeof loadDashboard === 'function') loadDashboard();
  } catch (e) {
    alert('Erreur reseau : ' + e.message);
  }
}

async function deleteCapitalFlow(id) {
  if (!confirm('Supprimer ce flux ?')) return;
  try {
    const res = await (typeof apiFetch === 'function'
      ? apiFetch('/api/portfolio/capital-flow/' + id, {method: 'DELETE'})
      : fetch('/api/portfolio/capital-flow/' + id, {method: 'DELETE'}));
    if (!res.ok) {
      alert('Erreur suppression');
      return;
    }
    await loadCapitalFlowsList();
    if (typeof loadDashboard === 'function') loadDashboard();
  } catch (e) {
    alert('Erreur : ' + e.message);
  }
}

window.openCapitalFlowModal = openCapitalFlowModal;
window.closeCapitalFlowModal = closeCapitalFlowModal;
window.submitCapitalFlow = submitCapitalFlow;
window.deleteCapitalFlow = deleteCapitalFlow;
'''
if "openCapitalFlowModal" in js:
    print("[SKIP] helpers capital flow deja presents")
else:
    js = js + capital_flow_js
    print("[OK] helpers capital flow ajoutes en fin de app.js")

# ============================================================
# Ecriture
# ============================================================
write_text(HTML, html)
write_text(JS, js)
print()
print(f"[OK] HTML ecrit ({len(html)} chars)")
print(f"[OK] JS   ecrit ({len(js)} chars)")
print()
print("DONE [FIX_UI_PNL_2FIELDS_AND_FLOWS_V1]")
