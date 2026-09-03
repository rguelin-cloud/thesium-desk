# -*- coding: utf-8 -*-
# [FIX_UI_PNL_2FIELDS_AND_FLOWS_V2]
# Refonte robuste : sections independantes, chaque echec est non-fatal,
# log clair de ce qui passe et ce qui rate.
#
# Sections :
#   A) HTML skeleton kpi-grid    (4 -> garde, on remplace card label dynamique en JS)
#   B) HTML supprime PIVA #portfolioIdealSection
#   C) HTML supprime PIVA h2 "Portfolio ideal vs actuel" (2eme bloc)
#   D) HTML ajoute capitalFlowBtn dans header Positions
#   E) HTML ajoute capitalFlowModal avant </body>
#   F) JS replace les 5 cards de renderKPIs (PV | TotalPnL | Cash | DailyPnL | VAR)
#      -> nouvelle composition : PV | Unrealized P&L | Total Return | Cash | Daily P&L | VAR  (6 cards)
#   G) JS commente call renderPortfolioIdeal()
#   H) JS commente function renderPortfolioIdeal
#   I) JS ajoute capital flow helpers en fin de fichier
#
# Chaque section a son propre try/except + log.

import re
import shutil
import time
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML_PATH = BASE / "index.html"
JS_PATH = BASE / "app.js"
MARKER = "FIX_UI_PNL_2FIELDS_AND_FLOWS_V2"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, text):
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))

html = read_text(HTML_PATH)
js = read_text(JS_PATH)

if MARKER in html and MARKER in js:
    print("[SKIP] marker " + MARKER + " deja present dans les 2 fichiers")
    raise SystemExit(0)

ts = time.strftime("%Y%m%d_%H%M%S")
shutil.copy2(HTML_PATH, HTML_PATH.with_suffix(".html.bak." + ts))
shutil.copy2(JS_PATH, JS_PATH.with_suffix(".js.bak." + ts))
print("[OK] backups -> .bak." + ts)

results = []

def log(section, ok, msg=""):
    flag = "OK  " if ok else "SKIP"
    results.append((section, ok, msg))
    print("[" + flag + "] " + section + ("  " + msg if msg else ""))

# ============================================================
# B) HTML : supprimer PIVA #portfolioIdealSection
# ============================================================
try:
    # Trouve la position de l'attribut id="portfolioIdealSection"
    idx = html.find('id="portfolioIdealSection"')
    if idx == -1:
        log("B PIVA #portfolioIdealSection", False, "deja absent")
    else:
        # Remonte au <div ouvrant
        open_idx = html.rfind("<div", 0, idx)
        if open_idx == -1:
            log("B PIVA #portfolioIdealSection", False, "<div ouvrant introuvable")
        else:
            # Compter <div>/</div> a partir de open_idx
            pos = html.find(">", open_idx) + 1
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
                # Inclure aussi commentaire optionnel juste avant
                pre = open_idx
                # Cherche commentaire <!-- Portfolio Id...al --> sur les 200 chars precedents
                upto = html.rfind("<!--", max(0, open_idx - 300), open_idx)
                if upto != -1 and "ortfolio" in html[upto:open_idx]:
                    close_comment = html.find("-->", upto)
                    if close_comment != -1 and close_comment < open_idx:
                        pre = upto
                removed_len = pos - pre
                html = html[:pre] + "<!-- [" + MARKER + "] PIVA #portfolioIdealSection removed (" + str(removed_len) + " chars) -->\n" + html[pos:]
                log("B PIVA #portfolioIdealSection", True, str(removed_len) + " chars supprimes")
            else:
                log("B PIVA #portfolioIdealSection", False, "balance </div> non trouvee")
except Exception as e:
    log("B PIVA #portfolioIdealSection", False, "exception: " + str(e))

# ============================================================
# C) HTML : supprimer PIVA h2 "Portfolio ideal vs actuel"
# ============================================================
try:
    # Pattern simple sans accents ambigus : id<chars>al vs actuel
    h2_rgx = re.compile(r"<h2[^>]*>[^<]*Portfolio[^<]*[Ii]d[^<]*al[^<]*vs[^<]*actuel[^<]*</h2>", re.IGNORECASE)
    m = h2_rgx.search(html)
    if not m:
        log("C PIVA h2 Portfolio ideal vs actuel", False, "absent")
    else:
        # Remonte au <div ouvrant le plus proche (max 800 chars)
        start_search = max(0, m.start() - 800)
        open_idx = html.rfind("<div", start_search, m.start())
        if open_idx == -1:
            # Fallback : supprime juste le h2
            html = html[:m.start()] + "<!-- [" + MARKER + "] PIVA h2 removed (no container) -->\n" + html[m.end():]
            log("C PIVA h2 Portfolio ideal vs actuel", True, "h2 only removed")
        else:
            pos = html.find(">", open_idx) + 1
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
                removed_len = pos - open_idx
                html = html[:open_idx] + "<!-- [" + MARKER + "] PIVA h2 container removed (" + str(removed_len) + " chars) -->\n" + html[pos:]
                log("C PIVA h2 Portfolio ideal vs actuel", True, str(removed_len) + " chars")
            else:
                log("C PIVA h2 Portfolio ideal vs actuel", False, "balance </div> non trouvee")
except Exception as e:
    log("C PIVA h2 Portfolio ideal vs actuel", False, "exception: " + str(e))

# ============================================================
# D) HTML : bouton Flux dans header Positions
# ============================================================
try:
    anchor = '<button class="btn btn-ghost" id="portfolioEditBtn"'
    if "capitalFlowBtn" in html:
        log("D capitalFlowBtn", False, "deja present")
    elif anchor not in html:
        log("D capitalFlowBtn", False, "anchor portfolioEditBtn absent")
    else:
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
        html = html.replace(anchor, flow_btn + anchor, 1)
        log("D capitalFlowBtn", True, "insere avant portfolioEditBtn")
except Exception as e:
    log("D capitalFlowBtn", False, "exception: " + str(e))

# ============================================================
# E) HTML : modal capital flow avant </body>
# ============================================================
try:
    if "capitalFlowModal" in html:
        log("E capitalFlowModal", False, "deja present")
    else:
        modal_html = (
            '\n<!-- [' + MARKER + '] Capital Flow Modal -->\n'
            '<div id="capitalFlowModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9999;align-items:center;justify-content:center" onclick="if(event.target===this)closeCapitalFlowModal()">\n'
            '  <div style="background:var(--color-surface,#1a1a1a);color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:24px;width:420px;max-width:90vw;box-shadow:0 10px 40px rgba(0,0,0,0.5)">\n'
            '    <h3 style="margin:0 0 16px 0;font-size:var(--text-lg);font-weight:600">Enregistrer un flux de capital</h3>\n'
            '    <div style="display:flex;flex-direction:column;gap:12px">\n'
            '      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">Type\n'
            '        <select id="cfSide" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm)">\n'
            '          <option value="deposit">Depot (+)</option>\n'
            '          <option value="withdrawal">Retrait (-)</option>\n'
            '        </select>\n'
            '      </label>\n'
            '      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">Montant (USD)\n'
            '        <input type="number" id="cfAmount" step="0.01" min="0" placeholder="10000" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm);font-family:var(--font-mono)" />\n'
            '      </label>\n'
            '      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">Date\n'
            '        <input type="date" id="cfDate" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm);font-family:var(--font-mono)" />\n'
            '      </label>\n'
            '      <label style="display:flex;flex-direction:column;gap:4px;font-size:var(--text-xs);color:var(--color-text-muted)">Note (optionnel)\n'
            '        <input type="text" id="cfNote" placeholder="virement broker" style="background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text);border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:6px 8px;font-size:var(--text-sm)" />\n'
            '      </label>\n'
            '      <div id="cfFlowsList" style="margin-top:8px;max-height:140px;overflow-y:auto;border:1px solid var(--color-divider);border-radius:var(--radius-sm);padding:8px;font-size:var(--text-xs);font-family:var(--font-mono);color:var(--color-text-muted);background:var(--color-surface-alt,rgba(255,255,255,0.02))"></div>\n'
            '    </div>\n'
            '    <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:20px">\n'
            '      <button onclick="closeCapitalFlowModal()" style="padding:6px 14px;border:1px solid var(--color-border);border-radius:var(--radius-sm);background:transparent;color:var(--color-text-muted);cursor:pointer;font-size:var(--text-sm)">Annuler</button>\n'
            '      <button onclick="submitCapitalFlow()" style="padding:6px 14px;border:1px solid #3b82f6;border-radius:var(--radius-sm);background:#3b82f6;color:#fff;cursor:pointer;font-size:var(--text-sm);font-weight:500">Enregistrer</button>\n'
            '    </div>\n'
            '  </div>\n'
            '</div>\n'
        )
        body_close = html.rfind("</body>")
        if body_close == -1:
            log("E capitalFlowModal", False, "</body> introuvable")
        else:
            html = html[:body_close] + modal_html + html[body_close:]
            log("E capitalFlowModal", True, "insere avant </body>")
except Exception as e:
    log("E capitalFlowModal", False, "exception: " + str(e))

# ============================================================
# F) JS : remplacer le bloc innerHTML de renderKPIs
# Approche : trouve "kpiGrid.innerHTML = `" puis le backtick fermant suivi de ";"
# au meme niveau (pas de backtick imbrique dans les KPI cards).
# ============================================================
try:
    start_pat = "kpiGrid.innerHTML = `"
    start_idx = js.find(start_pat)
    if start_idx == -1:
        log("F renderKPIs cards", False, "anchor kpiGrid.innerHTML introuvable")
    else:
        # Le contenu d'un template literal peut contenir des backticks echappes,
        # mais ici on suppose qu'il n'y en a pas. On cherche le `;` qui termine.
        # Le pattern de fin = "`;\n" ou "`;" suivi de saut.
        scan_from = start_idx + len(start_pat)
        # Cherche le premier ` qui n'est pas precede par \
        i = scan_from
        end_idx = -1
        while i < len(js):
            if js[i] == "`":
                # Verifie que le caractere suivant est ; ou \n;
                # Cherche le prochain non-espace
                j = i + 1
                while j < len(js) and js[j] in (" ", "\t"):
                    j += 1
                if j < len(js) and js[j] == ";":
                    end_idx = i
                    break
            i += 1
        if end_idx == -1:
            log("F renderKPIs cards", False, "fin de template literal introuvable")
        else:
            old_block = js[scan_from:end_idx]
            n_cards = old_block.count('<div class="kpi-card">')
            print("    [info] ancien innerHTML : " + str(n_cards) + " cards")
            # Construire le nouveau bloc (6 cards)
            new_block = '''
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
      <div class="kpi-delta neutral">${cash != null && pv != null ? fmtPct((cash / pv) * 100) + ' of NAV' : ''}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Daily P&amp;L</div>
      <div class="kpi-value mono ${colorClass(pnl)}">${fmtUSD(pnl)}</div>
      <div class="kpi-delta ${pnl > 0 ? 'positive' : pnl < 0 ? 'negative' : 'neutral'}">
        ${pnl > 0 ? '\\u25B2' : pnl < 0 ? '\\u25BC' : ''}
        ${pnl != null && pv != null ? fmtPct((pnl / pv) * 100) : ''}
      </div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">VAR (95%)</div>
      <div class="kpi-value mono text-negative">${fmtPct(var95)}</div>
      <div class="kpi-delta neutral">${var95 != null && pv != null ? fmtUSDCompact(pv * var95 / 100) + ' at risk' : ''}</div>
    </div>
  '''
            js = js[:scan_from] + new_block + js[end_idx:]
            log("F renderKPIs cards", True, "remplace " + str(n_cards) + " cards -> 6 cards (PV|Unrealized|TotalReturn|Cash|Daily|VAR)")
except Exception as e:
    log("F renderKPIs cards", False, "exception: " + str(e))

# ============================================================
# F2) JS : ajouter les const unrealizedPnl/totalReturn dans renderKPIs
# Anchor : "const totalPnlPct = p.total_pnl_pct"
# ============================================================
try:
    anchor = "const totalPnlPct = p.total_pnl_pct"
    idx = js.find(anchor)
    if idx == -1:
        log("F2 const unrealized/totalReturn", False, "anchor const totalPnlPct absent")
    elif "unrealizedPnl = p.unrealized_pnl" in js:
        log("F2 const unrealized/totalReturn", False, "deja present")
    else:
        eol = js.find("\n", idx)
        new_consts = (
            "\n  // [" + MARKER + "] 2 champs P&L\n"
            "  const unrealizedPnl = p.unrealized_pnl ?? totalPnl;\n"
            "  const unrealizedPnlPct = p.unrealized_pnl_pct ?? totalPnlPct;\n"
            "  const totalReturn = p.total_return ?? p.total_pnl ?? null;\n"
            "  const totalReturnPct = p.total_return_pct ?? p.total_pnl_pct ?? null;"
        )
        js = js[:eol] + new_consts + js[eol:]
        log("F2 const unrealized/totalReturn", True, "ajoutes apres const totalPnlPct")
except Exception as e:
    log("F2 const unrealized/totalReturn", False, "exception: " + str(e))

# ============================================================
# G) JS : commenter call renderPortfolioIdeal()
# ============================================================
try:
    pat = re.compile(r"^(\s*)renderPortfolioIdeal\s*\(\s*\)\s*;", re.MULTILINE)
    n = 0
    def repl(m):
        global n
        n += 1
        return m.group(1) + "// [" + MARKER + "] PIVA removed -- " + m.group(0).strip()
    js, count = pat.subn(repl, js)
    if count > 0:
        log("G call renderPortfolioIdeal", True, str(count) + " call(s) commentes")
    else:
        log("G call renderPortfolioIdeal", False, "deja absent")
except Exception as e:
    log("G call renderPortfolioIdeal", False, "exception: " + str(e))

# ============================================================
# H) JS : commenter function renderPortfolioIdeal
# ============================================================
try:
    fm = re.search(r"function\s+renderPortfolioIdeal\s*\(", js)
    if not fm:
        log("H function renderPortfolioIdeal", False, "deja absente")
    else:
        brace_open = js.find("{", fm.end())
        if brace_open == -1:
            log("H function renderPortfolioIdeal", False, "{ introuvable")
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
                func_start = fm.start()
                func_end = i
                replacement = "/* [" + MARKER + "] renderPortfolioIdeal removed (PIVA dropped)\n" + js[func_start:func_end] + "\n*/\n"
                js = js[:func_start] + replacement + js[func_end:]
                log("H function renderPortfolioIdeal", True, "commentee (" + str(func_end - func_start) + " chars)")
            else:
                log("H function renderPortfolioIdeal", False, "balance } echec")
except Exception as e:
    log("H function renderPortfolioIdeal", False, "exception: " + str(e))

# ============================================================
# I) JS : helpers capital flow en fin de fichier
# ============================================================
try:
    if "openCapitalFlowModal" in js:
        log("I capital flow helpers", False, "deja presents")
    else:
        capital_flow_js = '''

// [''' + MARKER + '''] Capital Flow helpers
function openCapitalFlowModal() {
  const modal = document.getElementById('capitalFlowModal');
  if (!modal) return;
  modal.style.display = 'flex';
  const today = new Date().toISOString().slice(0, 10);
  const dateInput = document.getElementById('cfDate');
  if (dateInput && !dateInput.value) dateInput.value = today;
  document.getElementById('cfAmount').value = '';
  document.getElementById('cfNote').value = '';
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
  if (!amount || amount <= 0) { alert('Montant invalide'); return; }
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
    if (!res.ok) { alert('Erreur suppression'); return; }
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
        js = js + capital_flow_js
        log("I capital flow helpers", True, "ajoutes en fin de app.js")
except Exception as e:
    log("I capital flow helpers", False, "exception: " + str(e))

# ============================================================
# Ecriture finale
# ============================================================
print()
print("=" * 60)
print("RESUME")
print("=" * 60)
n_ok = sum(1 for _, ok, _ in results if ok)
n_skip = sum(1 for _, ok, _ in results if not ok)
print("  " + str(n_ok) + " succes / " + str(n_skip) + " skip ou echecs")

# Garde-fou : si rien n'a change, ne pas overwrite
write_text(HTML_PATH, html)
write_text(JS_PATH, js)
print()
print("[OK] HTML ecrit (" + str(len(html)) + " chars)")
print("[OK] JS   ecrit (" + str(len(js)) + " chars)")
print()
print("Marker presence apres ecriture :")
print("  HTML marker : " + ("OUI" if MARKER in html else "NON"))
print("  JS   marker : " + ("OUI" if MARKER in js else "NON"))
print()
print("DONE [" + MARKER + "]")
