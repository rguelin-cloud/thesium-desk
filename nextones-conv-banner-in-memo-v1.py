# -*- coding: utf-8 -*-
"""
nextones-conv-banner-in-memo-v1
Injecte une banniere 'Verdict Convergence' en tete du modal Memo IA.

Strategie : wrapper window.pplxMemoOpen
  -> fetch /api/convergence/snapshot?ticker=<symbol> en parallele du chargement memo
  -> observer pplxMemoBody jusqu'a ce qu'il contienne le memo
  -> prepend la banniere

Marker : // [CONV_BANNER_IN_MEMO_V1]
Idempotent.
Append en fin de app.js.
"""
import os, sys, io, shutil, re
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
APP_JS = os.path.join(BASE, "app.js")
INDEX = os.path.join(BASE, "index.html")

JS_MARKER = "// [CONV_BANNER_IN_MEMO_V1]"
CSS_MARKER = "<!-- [CONV_BANNER_CSS_V1] -->"

# ----- CSS additionnel ------------------------------------------------------
CSS_BLOCK = """
<!-- [CONV_BANNER_CSS_V1] -->
<style>
  .conv-verdict-banner {
    margin: 0 0 14px 0;
    padding: 12px 14px;
    border-radius: 8px;
    border: 1px solid transparent;
    font-size: 13px;
    line-height: 1.45;
  }
  .conv-verdict-banner .cvb-head {
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .conv-verdict-banner .cvb-label {
    font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; font-size: 11px;
    padding: 2px 8px; border-radius: 10px;
  }
  .conv-verdict-banner .cvb-sizing {
    font-family: monospace; font-weight: 700; font-size: 14px;
  }
  .conv-verdict-banner .cvb-meta {
    font-size: 12px; color: inherit; opacity: 0.85;
  }
  .conv-verdict-banner .cvb-buckets {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 6px 14px; margin-top: 4px;
  }
  .conv-verdict-banner .cvb-bucket { display: flex; gap: 6px; align-items: baseline; }
  .conv-verdict-banner .cvb-dot {
    width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex-shrink: 0;
    border: 1px solid rgba(0,0,0,0.15);
  }
  .conv-verdict-banner .cvb-dot.long { background:#2ea043; }
  .conv-verdict-banner .cvb-dot.short { background:#e53935; }
  .conv-verdict-banner .cvb-dot.neutral { background:#8c959f; }
  .conv-verdict-banner .cvb-dot.absent { background:transparent; border-color:#8c959f; }
  .conv-verdict-banner .cvb-bucket-text {
    font-size: 11px; line-height: 1.3;
  }
  .conv-verdict-banner .cvb-bucket-key { font-weight: 600; }

  /* color schemes per verdict */
  .conv-verdict-banner.forced_exit { background: rgba(229,57,53,0.12); border-color: rgba(229,57,53,0.4); }
  .conv-verdict-banner.forced_exit .cvb-label { background: #e53935; color: #fff; }
  .conv-verdict-banner.forced_exit .cvb-sizing { color: #e53935; }
  .conv-verdict-banner.drift { background: rgba(212,167,44,0.12); border-color: rgba(212,167,44,0.4); }
  .conv-verdict-banner.drift .cvb-label { background: #d4a72c; color: #1f2328; }
  .conv-verdict-banner.drift .cvb-sizing { color: #b48400; }
  .conv-verdict-banner.strong { background: rgba(46,160,67,0.12); border-color: rgba(46,160,67,0.4); }
  .conv-verdict-banner.strong .cvb-label { background: #2ea043; color: #fff; }
  .conv-verdict-banner.strong .cvb-sizing { color: #2ea043; }
  .conv-verdict-banner.neutral_stable,
  .conv-verdict-banner.strong_neutral,
  .conv-verdict-banner.neutral,
  .conv-verdict-banner.conflict {
    background: rgba(125,133,144,0.10); border-color: rgba(125,133,144,0.3);
  }
  .conv-verdict-banner.neutral_stable .cvb-label,
  .conv-verdict-banner.strong_neutral .cvb-label,
  .conv-verdict-banner.neutral .cvb-label,
  .conv-verdict-banner.conflict .cvb-label {
    background: #7d8590; color: #fff;
  }
  .conv-verdict-banner.neutral_stable .cvb-sizing,
  .conv-verdict-banner.strong_neutral .cvb-sizing,
  .conv-verdict-banner.neutral .cvb-sizing,
  .conv-verdict-banner.conflict .cvb-sizing { color: #656d76; }

  /* texte par theme */
  html[data-theme="dark"] .conv-verdict-banner { color: #e6edf3; }
  html[data-theme="light"] .conv-verdict-banner { color: #1f2328; }
  html[data-theme="dark"] .conv-verdict-banner .cvb-meta { color: #c9d1d9; }
  html[data-theme="light"] .conv-verdict-banner .cvb-meta { color: #4d535b; }
</style>
"""

# ----- JS : wrapper + observer ----------------------------------------------
JS_BLOCK = r"""
// [CONV_BANNER_IN_MEMO_V1]
(function(){
  if (typeof window === 'undefined' || !window.pplxMemoOpen) {
    // attendre que pplxMemoOpen existe (defini plus haut dans le meme app.js, mais on est defensif)
    let _attempts = 0;
    const _wait = () => {
      _attempts++;
      if (window.pplxMemoOpen) { _install(); return; }
      if (_attempts < 50) setTimeout(_wait, 100);
    };
    setTimeout(_wait, 100);
  } else {
    _install();
  }

  const LABELS = {
    L1: "L1 Regime (Macro)",
    L2: "L2 Positioning (Factor)",
    L3: "L3 Structure (Micro)",
    L4: "L4 Liquidite (AltData)",
    L5: "L5 Risque (Exit)"
  };

  function _esc(s){
    if (s == null) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function _regimeLabel(row){
    if (row.regime_label) return row.regime_label;
    if (row.forced_exit) return "forced_exit";
    if (row.drift) return "drift";
    const m = row.sizing_multiplier || 0;
    const n = row.n_aligned || 0;
    if (m >= 1.0 && n >= 3) return "strong";
    if (row.direction_consensus === "conflict") return "conflict";
    return "neutral";
  }

  function _formatSizing(m){
    if (m == null) return "x1.0";
    return "x" + Number(m).toFixed(1);
  }

  function _renderBanner(row){
    const verdict = _regimeLabel(row);
    const sizing = _formatSizing(row.sizing_multiplier);
    const pct = row.convergence_pct == null ? 0 : Math.round(row.convergence_pct * 100);
    const dir = row.direction_consensus || "neutral";
    const buckets = row.buckets || {};
    const bucketsHtml = ["L1","L2","L3","L4","L5"].map(k => {
      const b = buckets[k];
      if (!b) {
        return '<div class="cvb-bucket"><span class="cvb-dot absent"></span><div class="cvb-bucket-text"><span class="cvb-bucket-key">'+LABELS[k]+'</span> : absent</div></div>';
      }
      const cls = (b.direction === "long" || b.direction === "short" || b.direction === "neutral") ? b.direction : "neutral";
      const driver = b.driver || "";
      return '<div class="cvb-bucket"><span class="cvb-dot '+cls+'"></span><div class="cvb-bucket-text"><span class="cvb-bucket-key">'+LABELS[k]+'</span> : '+_esc(b.direction || "?")+(driver ? ' - '+_esc(driver) : '')+'</div></div>';
    }).join("");

    return ''
      + '<div class="conv-verdict-banner '+verdict+'" data-conv-banner="1">'
      + '  <div class="cvb-head">'
      + '    <span class="cvb-label">Verdict systeme - '+verdict.replace("_"," ")+'</span>'
      + '    <span class="cvb-sizing">sizing '+sizing+'</span>'
      + '    <span class="cvb-meta">consensus '+_esc(dir)+' - '+(row.n_aligned||0)+'/'+(row.n_present||0)+' agents alignes - '+pct+'%</span>'
      + '  </div>'
      + '  <div class="cvb-buckets">'+bucketsHtml+'</div>'
      + '</div>';
  }

  async function _fetchConvForTicker(symbol){
    try {
      // Pas de filtre serveur par ticker pour l'instant : on prend tout puis on filtre
      const data = await apiFetch("/api/convergence/snapshot");
      if (!data || data.status !== "ok") return null;
      const rows = data.rows || [];
      return rows.find(r => (r.ticker||"").toUpperCase() === (symbol||"").toUpperCase()) || null;
    } catch(e) {
      console.warn("[conv-banner] fetch erreur", e);
      return null;
    }
  }

  function _injectBanner(row){
    const body = document.getElementById("pplxMemoBody");
    if (!body) return false;
    if (body.querySelector('[data-conv-banner="1"]')) return true;  // deja injecte
    // attendre que le memo soit charge (pas en .pplx-memo-loading)
    const loadingEl = body.querySelector(".pplx-memo-loading");
    if (loadingEl && body.children.length === 1) return false;
    const html = _renderBanner(row);
    // injecter en premier enfant
    body.insertAdjacentHTML("afterbegin", html);
    return true;
  }

  function _install(){
    const originalOpen = window.pplxMemoOpen;
    window.pplxMemoOpen = async function(symbol, force){
      // lancer fetch convergence en parallele
      const convPromise = _fetchConvForTicker(symbol);
      // appeler l'original
      const ret = await originalOpen.call(this, symbol, force);
      // une fois le memo charge, on injecte la banniere
      const row = await convPromise;
      if (!row) return ret;

      // attendre le DOM rendu
      let attempts = 0;
      const tryInject = () => {
        if (_injectBanner(row)) return;
        attempts++;
        if (attempts < 40) setTimeout(tryInject, 100);
      };
      tryInject();

      // observer : si le memo se re-render (refresh), reinjecter
      const body = document.getElementById("pplxMemoBody");
      if (body && !body._convObserverInstalled) {
        const obs = new MutationObserver(() => {
          if (!body.querySelector('[data-conv-banner="1"]')) {
            // memo a ete re-render, reinjecter
            setTimeout(() => _injectBanner(row), 50);
          }
        });
        obs.observe(body, { childList: true, subtree: false });
        body._convObserverInstalled = true;
      }

      return ret;
    };
    console.log("[conv-banner] wrapper installe sur pplxMemoOpen");
  }
})();
"""

# ---------------------------------------------------------------------------
def patch_app_js():
    print(f"[APPJS] {APP_JS}")
    with open(APP_JS, "r", encoding="utf-8-sig") as f:
        js = f.read()
    print(f"[APPJS] {len(js)} chars")

    if JS_MARKER in js:
        print("[APPJS] SKIP : marker present")
        return False

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = APP_JS + f".bak-conv-banner-{ts}"
    shutil.copy2(APP_JS, bak)
    print(f"[APPJS] backup : {bak}")

    if not js.endswith("\n"):
        js += "\n"
    new_js = js + "\n" + JS_BLOCK + "\n"

    # balance accolades
    ob, cb = new_js.count("{"), new_js.count("}")
    op, cp = new_js.count("("), new_js.count(")")
    print(f"[APPJS] balance {{={ob}/{cb}  (={op}/{cp}")
    if ob != cb or op != cp:
        print("[APPJS] WARN : balance non equilibree (peut-etre dans strings, on poursuit)")

    with open(APP_JS, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_js)
    print(f"[APPJS] OK : +{len(new_js)-len(js)} chars")
    return True

def patch_index_html():
    print(f"\n[INDEX] {INDEX}")
    with open(INDEX, "r", encoding="utf-8-sig") as f:
        html = f.read()
    print(f"[INDEX] {len(html)} chars")

    if CSS_MARKER in html:
        print("[INDEX] SKIP : marker CSS present")
        return False

    m = re.search(r'</head>', html, re.IGNORECASE)
    if not m:
        print("[INDEX] ECHEC : </head> introuvable")
        return False

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = INDEX + f".bak-conv-banner-css-{ts}"
    shutil.copy2(INDEX, bak)
    print(f"[INDEX] backup : {bak}")

    new_html = html[:m.start()] + CSS_BLOCK + "\n" + html[m.start():]
    with open(INDEX, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_html)
    print(f"[INDEX] OK : +{len(new_html)-len(html)} chars")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("CONV BANNER IN MEMO V1")
    print("=" * 60)
    r1 = patch_app_js()
    r2 = patch_index_html()
    print()
    print(f"[RESULT] app.js: {'PATCHED' if r1 else 'SKIPPED'}   index.html: {'PATCHED' if r2 else 'SKIPPED'}")
    print("[NEXT] Hard-reload (Ctrl+F5), cliquer Memo IA sur AMD => banniere rouge visible en tete du modal")
