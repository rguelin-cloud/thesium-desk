# -*- coding: utf-8 -*-
"""
nextones-ui-convergence-card-v1
Injection UI Convergence Engine :
- index.html : carte HTML <section class="pplx-section" id="convergence-section"> AVANT pplx-thesis-section
- app.js : loadConvergenceSnapshot() + renderConvergenceCard() + hook DOMContentLoaded + setInterval 5min

Idempotent via markers :
  HTML : <!-- [CONVERGENCE_CARD_V1] -->
  JS   : // [CONVERGENCE_JS_V1]

Style : reutilise classes existantes (pplx-section, pplx-regime-badge), ajoute CSS scope conv-* en local.
"""
import os, sys, re, io, ast, py_compile, shutil
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
INDEX_PATH = os.path.join(BASE, "index.html")
APP_JS_PATH = os.path.join(BASE, "app.js")

HTML_MARKER = "<!-- [CONVERGENCE_CARD_V1] -->"
JS_MARKER = "// [CONVERGENCE_JS_V1]"

# ---------------------------------------------------------------------------
# Bloc HTML a inserer
# ---------------------------------------------------------------------------
HTML_BLOCK = """
<!-- [CONVERGENCE_CARD_V1] -->
<style>
  .conv-section { margin-top: 16px; padding: 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
  .conv-header { display:flex; justify-content:space-between; align-items:center; gap:12px; margin-bottom: 12px; flex-wrap: wrap; }
  .conv-title { display:flex; align-items:center; gap:10px; }
  .conv-title h3 { margin:0; font-size:16px; color:#e6edf3; font-weight:600; }
  .conv-cycle-meta { color:#7d8590; font-size:12px; }
  .conv-totals { display:flex; gap:14px; flex-wrap:wrap; font-size:12px; }
  .conv-totals span { color:#7d8590; }
  .conv-totals b { color:#e6edf3; font-weight:600; }
  .conv-totals .fe { color:#e53935; }
  .conv-totals .dr { color:#d4a72c; }
  .conv-totals .st { color:#2ea043; }
  .conv-totals .cf { color:#db6d28; }
  .conv-tabs { display:flex; gap:6px; margin-bottom:10px; border-bottom:1px solid #30363d; }
  .conv-tab { padding:6px 12px; cursor:pointer; color:#7d8590; font-size:13px; border-bottom:2px solid transparent; user-select:none; }
  .conv-tab:hover { color:#e6edf3; }
  .conv-tab.active { color:#e6edf3; border-bottom-color:#58a6ff; }
  .conv-table-wrap { overflow-x:auto; }
  table.conv-table { width:100%; border-collapse:collapse; font-size:13px; }
  table.conv-table th { text-align:left; padding:8px 6px; color:#7d8590; font-weight:500; border-bottom:1px solid #30363d; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; }
  table.conv-table td { padding:8px 6px; border-bottom:1px solid #21262d; color:#e6edf3; }
  table.conv-table tr:hover td { background:#1c2128; }
  .conv-ticker { font-weight:600; }
  .conv-ticker .crypto-badge { display:inline-block; margin-left:6px; padding:1px 5px; font-size:10px; background:#3a2a52; color:#c9a4ff; border-radius:3px; }
  .conv-buckets { display:flex; gap:4px; }
  .conv-dot { width:14px; height:14px; border-radius:50%; display:inline-block; border:1px solid #30363d; cursor:help; position:relative; }
  .conv-dot.long { background:#2ea043; border-color:#2ea043; }
  .conv-dot.short { background:#e53935; border-color:#e53935; }
  .conv-dot.neutral { background:#7d8590; border-color:#7d8590; }
  .conv-dot.absent { background:#0d1117; border-color:#30363d; }
  .conv-bucket-label { font-size:9px; color:#7d8590; display:block; text-align:center; margin-top:2px; }
  .conv-bucket-col { display:flex; flex-direction:column; align-items:center; }
  .conv-pct { color:#7d8590; }
  .conv-aligned { font-family:monospace; }
  .conv-sizing { font-family:monospace; font-weight:600; }
  .conv-sizing.x0 { color:#e53935; }
  .conv-sizing.x05 { color:#d4a72c; }
  .conv-sizing.x1 { color:#7d8590; }
  .conv-sizing.x12 { color:#2ea043; }
  .conv-regime { font-size:11px; padding:2px 8px; border-radius:10px; display:inline-block; }
  .conv-regime.forced_exit { background:rgba(229,57,53,0.18); color:#e53935; }
  .conv-regime.drift { background:rgba(212,167,44,0.18); color:#d4a72c; }
  .conv-regime.strong { background:rgba(46,160,67,0.18); color:#2ea043; }
  .conv-regime.conflict { background:rgba(219,109,40,0.18); color:#db6d28; }
  .conv-regime.neutral { background:rgba(125,133,144,0.18); color:#7d8590; }
  .conv-empty, .conv-loading { padding:20px; text-align:center; color:#7d8590; font-size:13px; }
  .conv-error { padding:12px; color:#e53935; font-size:13px; }
  .conv-dot[title]:hover::after {
    content: attr(title);
    position: absolute; bottom: calc(100% + 6px); left: 50%; transform: translateX(-50%);
    background: #0d1117; color:#e6edf3; padding:6px 10px; border-radius:4px; border:1px solid #30363d;
    font-size:11px; white-space:nowrap; z-index:1000; pointer-events:none;
  }
</style>
<section class="pplx-section conv-section" id="convergence-section" aria-label="Convergence Engine">
  <div class="conv-header">
    <div class="conv-title">
      <h3>Convergence Engine</h3>
      <span class="conv-cycle-meta" id="conv-cycle-meta">--</span>
    </div>
    <div class="conv-totals" id="conv-totals">
      <span><b id="conv-total-n">0</b> tickers</span>
      <span class="fe"><b id="conv-total-fe">0</b> forced_exit</span>
      <span class="dr"><b id="conv-total-dr">0</b> drift</span>
      <span class="st"><b id="conv-total-st">0</b> strong</span>
      <span class="cf"><b id="conv-total-cf">0</b> conflict</span>
      <span><b id="conv-total-nu">0</b> neutres</span>
    </div>
  </div>
  <div class="conv-tabs" id="conv-tabs">
    <div class="conv-tab active" data-conv-filter="all">Tous</div>
    <div class="conv-tab" data-conv-filter="forced_exit">Forced exit</div>
    <div class="conv-tab" data-conv-filter="strong">Strong</div>
  </div>
  <div class="conv-table-wrap">
    <table class="conv-table" id="conv-table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>L1 Regime</th>
          <th>L2 Position</th>
          <th>L3 Structure</th>
          <th>L4 Liquidite</th>
          <th>L5 Risque</th>
          <th>Consensus</th>
          <th>n_aligned</th>
          <th>Sizing</th>
          <th>Regime</th>
        </tr>
      </thead>
      <tbody id="conv-tbody">
        <tr><td colspan="10" class="conv-loading">Chargement de la convergence...</td></tr>
      </tbody>
    </table>
  </div>
</section>
"""

# ---------------------------------------------------------------------------
# Bloc JS a inserer dans app.js (avant la fin de fichier ou apres pplxBoot)
# ---------------------------------------------------------------------------
JS_BLOCK = r"""
// [CONVERGENCE_JS_V1]
(function(){
  let _convRows = [];
  let _convFilter = "all";

  const BUCKETS_ORDER = ["L1_regime","L2_positioning","L3_structure","L4_liquidite","L5_risque"];

  function _convDotClass(direction){
    if (direction === "long") return "long";
    if (direction === "short") return "short";
    if (direction === "neutral") return "neutral";
    return "absent";
  }

  function _convSizingClass(m){
    if (m === 0 || m < 0.01) return "x0";
    if (m < 0.7) return "x05";
    if (m < 1.05) return "x1";
    return "x12";
  }

  function _convFormatSizing(m){
    if (m === 0 || m == null) return "x0.0";
    return "x" + Number(m).toFixed(1);
  }

  function _convRegimeLabel(row){
    if (row.forced_exit === 1 || row.forced_exit === true) return "forced_exit";
    if (row.drift === 1 || row.drift === true) return "drift";
    const m = row.sizing_multiplier || 0;
    const n = row.n_aligned || 0;
    if (m >= 1.0 && n >= 3) return "strong";
    if (row.direction_consensus === "conflict") return "conflict";
    return "neutral";
  }

  function _convBucketCell(buckets, key){
    const b = (buckets || {})[key] || {};
    const dir = b.direction || "absent";
    const cls = _convDotClass(dir);
    const driver = b.driver || b.source || dir;
    const title = key.replace("_"," ") + " : " + dir + (driver && driver !== dir ? " (" + driver + ")" : "");
    return '<td><div class="conv-bucket-col"><span class="conv-dot ' + cls + '" title="' + _escHtml(title) + '"></span></div></td>';
  }

  function _escHtml(s){
    if (s == null) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function _convRenderRows(){
    const tbody = document.getElementById("conv-tbody");
    if (!tbody) return;
    let rows = _convRows.slice();
    if (_convFilter === "forced_exit") {
      rows = rows.filter(r => r.forced_exit === 1 || r.forced_exit === true);
    } else if (_convFilter === "strong") {
      rows = rows.filter(r => (r.sizing_multiplier >= 1.0) && (r.n_aligned >= 3));
    }
    if (rows.length === 0) {
      tbody.innerHTML = '<tr><td colspan="10" class="conv-empty">Aucun ticker pour ce filtre</td></tr>';
      return;
    }
    const html = rows.map(r => {
      const regimeLabel = r.regime_label || _convRegimeLabel(r);
      const sizing = r.sizing_multiplier == null ? 1.0 : Number(r.sizing_multiplier);
      const pct = r.convergence_pct == null ? 0 : Math.round(r.convergence_pct * 100);
      const cryptoBadge = (r.is_crypto === 1 || r.is_crypto === true) ? '<span class="crypto-badge">C</span>' : '';
      const buckets = r.buckets || {};
      const bucketCells = BUCKETS_ORDER.map(k => _convBucketCell(buckets, k)).join("");
      return '<tr>'
        + '<td class="conv-ticker">' + _escHtml(r.ticker) + cryptoBadge + '</td>'
        + bucketCells
        + '<td class="conv-pct">' + pct + '%</td>'
        + '<td class="conv-aligned">' + (r.n_aligned||0) + '/' + (r.n_present||0) + '</td>'
        + '<td class="conv-sizing ' + _convSizingClass(sizing) + '">' + _convFormatSizing(sizing) + '</td>'
        + '<td><span class="conv-regime ' + regimeLabel + '">' + regimeLabel + '</span></td>'
        + '</tr>';
    }).join("");
    tbody.innerHTML = html;
  }

  function _convRenderTotals(totals, cycleId, createdAt){
    document.getElementById("conv-total-n").textContent  = totals.n_tickers || 0;
    document.getElementById("conv-total-fe").textContent = totals.forced_exit || 0;
    document.getElementById("conv-total-dr").textContent = totals.drift || 0;
    document.getElementById("conv-total-st").textContent = totals.strong || 0;
    document.getElementById("conv-total-cf").textContent = totals.conflict || 0;
    document.getElementById("conv-total-nu").textContent = totals.neutral || 0;
    const meta = document.getElementById("conv-cycle-meta");
    if (meta) meta.textContent = "cycle " + (cycleId||"-") + (createdAt ? " - " + createdAt : "");
  }

  function _convSortRows(rows){
    return rows.sort((a,b) => {
      const fa = (a.forced_exit?1:0), fb = (b.forced_exit?1:0);
      if (fa !== fb) return fb - fa;
      const da = (a.drift?1:0), db = (b.drift?1:0);
      if (da !== db) return db - da;
      const ma = a.sizing_multiplier == null ? 1.0 : a.sizing_multiplier;
      const mb = b.sizing_multiplier == null ? 1.0 : b.sizing_multiplier;
      if (ma !== mb) return ma - mb;
      return (a.ticker||"").localeCompare(b.ticker||"");
    });
  }

  async function loadConvergenceSnapshot(){
    const tbody = document.getElementById("conv-tbody");
    if (!tbody) return;
    try {
      const data = await apiFetch("/api/convergence/snapshot");
      if (!data || data.status !== "ok") {
        tbody.innerHTML = '<tr><td colspan="10" class="conv-error">Reponse invalide</td></tr>';
        return;
      }
      _convRows = _convSortRows(data.rows || []);
      _convRenderTotals(data.totals || {}, data.cycle_id, data.created_at);
      _convRenderRows();
    } catch(e) {
      console.error("[convergence] load error", e);
      tbody.innerHTML = '<tr><td colspan="10" class="conv-error">Erreur : ' + _escHtml(e.message || e) + '</td></tr>';
    }
  }

  function _convBindTabs(){
    const tabs = document.querySelectorAll("#conv-tabs .conv-tab");
    tabs.forEach(t => {
      t.addEventListener("click", () => {
        tabs.forEach(x => x.classList.remove("active"));
        t.classList.add("active");
        _convFilter = t.getAttribute("data-conv-filter") || "all";
        _convRenderRows();
      });
    });
  }

  function _convBoot(){
    if (!document.getElementById("convergence-section")) return;
    _convBindTabs();
    loadConvergenceSnapshot();
    setInterval(loadConvergenceSnapshot, 5 * 60 * 1000);
  }

  window.loadConvergenceSnapshot = loadConvergenceSnapshot;
  document.addEventListener("DOMContentLoaded", _convBoot);
})();
"""

# ---------------------------------------------------------------------------
def patch_index_html():
    print(f"[INDEX] {INDEX_PATH}")
    with open(INDEX_PATH, "r", encoding="utf-8-sig") as f:
        html = f.read()
    print(f"[INDEX] {len(html)} chars, {len(html.split(chr(10)))} lignes")

    if HTML_MARKER in html:
        print("[INDEX] SKIP : marker present")
        return False

    # Cible : juste avant <div class="pplx-section" id="pplx-thesis-section">
    # Fallback : avant <div id="pplxMemoBackdrop"> ou avant </body>
    pat_thesis = re.compile(r'(\s*)(<div\s+class="pplx-section"\s+id="pplx-thesis-section">)', re.IGNORECASE)
    m = pat_thesis.search(html)
    insertion_point = None
    if m:
        insertion_point = m.start(2)
        print(f"[INDEX] cible : pplx-thesis-section @ offset {insertion_point}")
    else:
        pat_memo = re.compile(r'<div\s+id="pplxMemoBackdrop"', re.IGNORECASE)
        m = pat_memo.search(html)
        if m:
            insertion_point = m.start()
            print(f"[INDEX] FALLBACK : avant pplxMemoBackdrop @ {insertion_point}")
        else:
            pat_pplx_crypto = re.compile(r'<table\s+id="pplx-crypto-table"', re.IGNORECASE)
            m = pat_pplx_crypto.search(html)
            if m:
                # remonter au div parent (pplx-section qui contient cette table)
                # plus simple : injecter avant la table
                insertion_point = m.start()
                print(f"[INDEX] FALLBACK2 : avant pplx-crypto-table @ {insertion_point}")

    if insertion_point is None:
        print("[INDEX] ECHEC : aucun point d'ancrage trouve")
        return False

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = INDEX_PATH + f".bak-conv-card-{ts}"
    shutil.copy2(INDEX_PATH, bak)
    print(f"[INDEX] backup : {bak}")

    new_html = html[:insertion_point] + HTML_BLOCK + "\n" + html[insertion_point:]

    with open(INDEX_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_html)
    print(f"[INDEX] OK : +{len(new_html) - len(html)} chars")
    return True

def patch_app_js():
    print(f"\n[APPJS] {APP_JS_PATH}")
    with open(APP_JS_PATH, "r", encoding="utf-8-sig") as f:
        js = f.read()
    print(f"[APPJS] {len(js)} chars, {len(js.split(chr(10)))} lignes")

    if JS_MARKER in js:
        print("[APPJS] SKIP : marker present")
        return False

    # On append en fin de fichier (IIFE, scope isole)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = APP_JS_PATH + f".bak-conv-js-{ts}"
    shutil.copy2(APP_JS_PATH, bak)
    print(f"[APPJS] backup : {bak}")

    if not js.endswith("\n"):
        js += "\n"
    new_js = js + "\n" + JS_BLOCK + "\n"

    # Pas d'AST python ici - simple validation : balance accolades/parentheses
    open_b = new_js.count("{")
    close_b = new_js.count("}")
    open_p = new_js.count("(")
    close_p = new_js.count(")")
    print(f"[APPJS] balance : {{={open_b}/{close_b}  (={open_p}/{close_p}")
    if open_b != close_b or open_p != close_p:
        print("[APPJS] WARN : balance disequilibree (peut-etre dans des strings)")

    with open(APP_JS_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_js)
    print(f"[APPJS] OK : +{len(new_js) - len(js)} chars")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("CONVERGENCE CARD V1 - INJECTION UI")
    print("=" * 60)
    r1 = patch_index_html()
    r2 = patch_app_js()
    print()
    print(f"[RESULT] index.html: {'PATCHED' if r1 else 'SKIPPED'}   app.js: {'PATCHED' if r2 else 'SKIPPED'}")
    print("[NEXT] Restart uvicorn + hard-reload navigateur (Ctrl+F5)")
