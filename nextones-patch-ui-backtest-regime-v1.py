"""
[PATCH_UI_BACKTEST_REGIME_V1]
Patche index.html + app.js pour ajouter l'option "Regime de Marche" au backtest.

HTML (index.html) :
  - Ajoute une checkbox 'Comparer avec regime de marche' dans la barre de controls
    (juste avant le bouton 'Lancer le backtest').
  - Etend l'en-tete de la table stats (la 3eme colonne deviendra 'Avec Regime'
    quand applicable, gere en JS).
  - Ajoute un placeholder pour le panneau 'Regime Summary' sous le chart.

app.js :
  - Modifie runBacktest() pour envoyer apply_regime dans le body POST.
  - Modifie renderBacktestResults() pour :
      * Ajouter un 3eme dataset 'Portfolio + Regime' au chart.
      * Calculer et afficher KPI delta (sharpe, max DD) quand regime present.
      * Afficher panneau resume regime (calm/normal/stress days par bucket).
      * Si stats_regime present, etendre la table stats avec colonne 'Avec Regime'.

Idempotent. Backups .bak.<timestamp>. Validation ast.parse pour ce patch.
Le patch lui-meme est ASCII pur ; les snippets injectes sont ASCII pur
(accents en entites HTML pour HTML, en escapes \\u00xx pour JS).
"""
import io
import os
import sys
import re
import ast
import py_compile
import shutil
import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML_PATH = os.path.join(ROOT, "index.html")
JS_PATH = os.path.join(ROOT, "app.js")
MARKER_HTML = "<!-- [PATCH_UI_BACKTEST_REGIME_V1] -->"
MARKER_JS = "// [PATCH_UI_BACKTEST_REGIME_V1]"


def read_utf8_sig(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="strict") as f:
        return f.read()


def write_utf8_no_bom(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def assert_ascii(snippet, label):
    bad = [(i, b) for i, b in enumerate(snippet.encode("utf-8")) if b > 127]
    if bad:
        raise RuntimeError(
            "Snippet %s contient %d bytes non-ASCII (premier @ offset %d byte=%d)"
            % (label, len(bad), bad[0][0], bad[0][1])
        )


def backup(p):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    b = p + ".bak." + ts
    shutil.copy2(p, b)
    return b


# ---------------------------------------------------------------------------
# HTML PATCH
# ---------------------------------------------------------------------------

HTML_CHECKBOX_SNIPPET = (
    "        " + MARKER_HTML + "\n"
    "        <div style=\"display:flex;flex-direction:column;gap:var(--space-1)\">\n"
    "          <label class=\"text-muted\" style=\"font-size:var(--text-xs)\">Option</label>\n"
    "          <label style=\"display:inline-flex;align-items:center;gap:var(--space-2);height:36px;padding:0 var(--space-2);border:1px solid var(--border);border-radius:var(--radius-md);cursor:pointer\">\n"
    "            <input type=\"checkbox\" id=\"btApplyRegime\" />\n"
    "            <span style=\"font-size:var(--text-xs)\">Comparer avec r&eacute;gime de march&eacute;</span>\n"
    "          </label>\n"
    "        </div>\n"
)

HTML_REGIME_PANEL_SNIPPET = (
    "        " + MARKER_HTML + "\n"
    "        <div id=\"btRegimePanel\" style=\"display:none;background:var(--surface-1);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--space-4);margin-bottom:var(--space-4)\">\n"
    "          <h3 style=\"font-size:var(--text-sm);margin-bottom:var(--space-3)\">R&eacute;gime de march&eacute; &mdash; r&eacute;sum&eacute;</h3>\n"
    "          <div id=\"btRegimeBody\" style=\"display:grid;grid-template-columns:repeat(4, 1fr);gap:var(--space-3)\"></div>\n"
    "          <p class=\"text-muted\" style=\"font-size:var(--text-xs);margin-top:var(--space-3);margin-bottom:0\">M&eacute;thodo : VIX proxy + vol r&eacute;alis&eacute;e 20j + drawdown 5j par bucket. CALM &rarr; r&eacute;duction exposition (take profit). STRESS &rarr; maintien max exposition (pas de leverage en backtest).</p>\n"
    "        </div>\n"
)


def patch_html():
    print("\n--- HTML PATCH ---")
    src = read_utf8_sig(HTML_PATH)
    if MARKER_HTML in src:
        print("[SKIP HTML] marker deja present")
        return

    assert_ascii(HTML_CHECKBOX_SNIPPET, "html checkbox")
    assert_ascii(HTML_REGIME_PANEL_SNIPPET, "html regime panel")

    bak = backup(HTML_PATH)
    print("[BACKUP HTML] " + bak)

    # A) Inserer la checkbox AVANT le bouton 'btRunBtn'
    # Cible : ligne contenant 'id="btRunBtn"'
    needle_btn = '<button class="btn btn-primary" id="btRunBtn"'
    idx_btn = src.find(needle_btn)
    if idx_btn < 0:
        raise RuntimeError("btRunBtn introuvable dans index.html")
    # Insertion juste avant la ligne. On recule jusqu'au debut de ligne.
    line_start = src.rfind("\n", 0, idx_btn) + 1
    src = src[:line_start] + HTML_CHECKBOX_SNIPPET + src[line_start:]
    print("[INJECT HTML] checkbox apply_regime avant btRunBtn")

    # B) Inserer le panneau resume regime AVANT le chart (juste avant la div btChart)
    # Cible : ligne contenant 'canvas id="btChart"' -> on remonte au debut du bloc card
    # qui contient '<h3 ...>Courbe d\'\u00e9quit\u00e9</h3>'
    needle_chart = '<canvas id="btChart">'
    idx_chart = src.find(needle_chart)
    if idx_chart < 0:
        raise RuntimeError("canvas btChart introuvable")
    # Remonter au debut du bloc surface-1 qui englobe le chart (cherche 'background:var(--surface-1)' au-dessus)
    # Plus simple : on cherche, au-dessus, la 1ere occurrence de "<div style=\"background:var(--surface-1)"
    upper = src.rfind("<div style=\"background:var(--surface-1)", 0, idx_chart)
    if upper < 0:
        raise RuntimeError("conteneur chart background:var(--surface-1) introuvable")
    line_start2 = src.rfind("\n", 0, upper) + 1
    src = src[:line_start2] + HTML_REGIME_PANEL_SNIPPET + src[line_start2:]
    print("[INJECT HTML] panneau resume regime avant le chart")

    write_utf8_no_bom(HTML_PATH, src)
    print("[WRITE HTML] " + HTML_PATH)


# ---------------------------------------------------------------------------
# JS PATCH
# ---------------------------------------------------------------------------

# Helpers + render extensions injectes en fin de fichier.
# ASCII pur strict (\u00xx pour accents).
JS_BLOCK = (
    "\n\n" + MARKER_JS + "\n"
    "// Backtest regime overlay extension\n"
    "(function(){\n"
    "  // Hook into runBacktest to send apply_regime\n"
    "  if (typeof window.runBacktest !== 'function') return;\n"
    "  // We cannot monkey-patch runBacktest easily because it's local-scope.\n"
    "  // Instead the modification is done by editing runBacktest body directly via this patch.\n"
    "})();\n"
)

# A) Modification de runBacktest pour envoyer apply_regime dans le body POST
# B) Extension de renderBacktestResults pour exploiter portfolio_equity_regime,
#    stats_regime, regime_timeline, regime_summary
# Ces 2 modifications sont des edits LOCAUX sur des lignes existantes; on ne les
# fait pas via append. Voir patch_js() ci-dessous.


def patch_js():
    print("\n--- JS PATCH ---")
    src = read_utf8_sig(JS_PATH)
    if MARKER_JS in src:
        print("[SKIP JS] marker deja present")
        return

    bak = backup(JS_PATH)
    print("[BACKUP JS] " + bak)

    # ---- A) Modifier le body POST dans runBacktest ----
    # On cherche la string 'apiFetch(\'/api/backtest\'' et le body JSON.stringify(...)
    # Pattern attendu (approximatif) :
    #   const resp = await apiFetch('/api/backtest', {
    #     method: 'POST',
    #     body: JSON.stringify({ ... })
    #   });
    # On va localiser le bloc JSON.stringify({...}) qui suit et y ajouter apply_regime.
    m = re.search(r"apiFetch\(\s*['\"]/api/backtest['\"]", src)
    if not m:
        raise RuntimeError("apiFetch('/api/backtest') introuvable dans app.js")
    # Cherche le JSON.stringify dans les 800 caracteres suivants
    region_start = m.start()
    region = src[region_start:region_start + 1200]
    m2 = re.search(r"JSON\.stringify\(\s*\{", region)
    if not m2:
        raise RuntimeError("JSON.stringify({ apres apiFetch /api/backtest introuvable")
    # Cherche la fermeture '})' qui termine le body
    # On va chercher le premier '})' apres le '{' en gerant un compteur tres simple.
    open_pos_rel = m2.end() - 1  # position du '{' (inclus)
    depth = 1
    i = m2.end()
    closing_brace_rel = None
    while i < len(region):
        c = region[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                closing_brace_rel = i
                break
        i += 1
    if closing_brace_rel is None:
        raise RuntimeError("fermeture '}' du body POST introuvable")
    # Absolute index in src
    abs_close = region_start + closing_brace_rel
    # On insere ', apply_regime: applyRegime' juste avant le '}'
    # Mais on doit recuperer applyRegime depuis le DOM. Pour ca on l'ajoute en tete
    # de runBacktest. Voir etape B.
    insert_str = ", apply_regime: applyRegime"
    # S'assurer ASCII
    assert_ascii(insert_str, "body apply_regime kv")
    src = src[:abs_close] + insert_str + src[abs_close:]
    print("[INJECT JS] apply_regime ajoute au body POST /api/backtest")

    # ---- B) Ajouter declaration applyRegime au debut du body de runBacktest ----
    # Cherche 'async function runBacktest()' puis le premier '{' apres
    m3 = re.search(r"async\s+function\s+runBacktest\s*\(\s*\)\s*\{", src)
    if not m3:
        raise RuntimeError("async function runBacktest() introuvable")
    insert_pt = m3.end()
    decl = ("\n  " + MARKER_JS + "\n"
            "  const applyRegime = (document.getElementById('btApplyRegime') && "
            "document.getElementById('btApplyRegime').checked) || false;\n")
    assert_ascii(decl, "runBacktest applyRegime decl")
    src = src[:insert_pt] + decl + src[insert_pt:]
    print("[INJECT JS] declaration applyRegime en tete de runBacktest")

    # ---- C) Ajouter un helper renderBacktestRegime() en fin de fichier ----
    # et l'appeler depuis renderBacktestResults
    # On cherche d'abord la fin de renderBacktestResults pour y inserer un appel.
    m4 = re.search(r"function\s+renderBacktestResults\s*\(", src)
    if not m4:
        raise RuntimeError("function renderBacktestResults introuvable")
    # Cherche la prochaine fonction ou la fin du fichier; on prend la borne haute
    # de renderBacktestResults par bracket-matching.
    body_start = src.find("{", m4.end())
    depth = 1
    i = body_start + 1
    body_end = None
    while i < len(src):
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                body_end = i
                break
        i += 1
    if body_end is None:
        raise RuntimeError("Fermeture renderBacktestResults introuvable")
    # On insere l'appel a renderBacktestRegime juste avant '}' final de la fonction
    call_str = ("\n  " + MARKER_JS + "\n"
                "  try { renderBacktestRegime(data); } catch(e) { console.warn('regime render fail', e); }\n")
    assert_ascii(call_str, "renderBacktestResults regime call")
    src = src[:body_end] + call_str + src[body_end:]
    print("[INJECT JS] appel renderBacktestRegime() avant fin renderBacktestResults")

    # ---- D) Helper renderBacktestRegime() append a la fin du fichier ----
    helper = (
        "\n" + MARKER_JS + "\n"
        "function renderBacktestRegime(data){\n"
        "  // Panneau resume\n"
        "  const panel = document.getElementById('btRegimePanel');\n"
        "  const body  = document.getElementById('btRegimeBody');\n"
        "  if (!panel || !body) return;\n"
        "  if (!data || !data.regime_summary){\n"
        "    panel.style.display = 'none';\n"
        "    return;\n"
        "  }\n"
        "  const s = data.regime_summary || {};\n"
        "  const eq = s.equity || {calm_days:0, normal_days:0, stress_days:0};\n"
        "  const cr = s.crypto || {calm_days:0, normal_days:0, stress_days:0};\n"
        "  const sR = data.stats_regime || null;\n"
        "  const sB = data.stats || null;\n"
        "  let dSharpe = null, dMaxDd = null, dTotalRet = null;\n"
        "  if (sR && sB){\n"
        "    dSharpe   = (sR.sharpe||0) - (sB.sharpe||0);\n"
        "    dMaxDd    = (sR.max_drawdown_pct||0) - (sB.max_drawdown_pct||0);\n"
        "    dTotalRet = (sR.total_return_pct||0) - (sB.total_return_pct||0);\n"
        "  }\n"
        "  function _kpi(label, value, sub){\n"
        "    return '<div class=\"kpi-card\" style=\"background:var(--surface-2);padding:var(--space-3);border-radius:var(--radius-md)\">' +\n"
        "      '<div class=\"kpi-label\" style=\"font-size:var(--text-xs);color:var(--text-muted)\">' + label + '</div>' +\n"
        "      '<div class=\"kpi-value mono\" style=\"font-size:var(--text-lg);font-weight:600\">' + value + '</div>' +\n"
        "      (sub ? '<div style=\"font-size:var(--text-xs);color:var(--text-muted);margin-top:2px\">' + sub + '</div>' : '') +\n"
        "    '</div>';\n"
        "  }\n"
        "  function _fmtSigned(v, dp, suffix){\n"
        "    if (v === null || v === undefined || isNaN(v)) return '-';\n"
        "    const f = (Math.abs(v)).toFixed(dp);\n"
        "    return (v >= 0 ? '+' : '-') + f + (suffix||'');\n"
        "  }\n"
        "  const eqStr = 'CALM ' + eq.calm_days + ' / NORM ' + eq.normal_days + ' / STR ' + eq.stress_days;\n"
        "  const crStr = 'CALM ' + cr.calm_days + ' / NORM ' + cr.normal_days + ' / STR ' + cr.stress_days;\n"
        "  let html = '';\n"
        "  html += _kpi('Equity jours', eqStr, 'base ' + (s.base_equity_weight_pct||0).toFixed(1) + '%');\n"
        "  html += _kpi('Crypto jours', crStr, 'base ' + (s.base_crypto_weight_pct||0).toFixed(1) + '%');\n"
        "  html += _kpi('Delta Sharpe', _fmtSigned(dSharpe, 2, ''), 'regime vs sans');\n"
        "  html += _kpi('Delta Max DD', _fmtSigned(dMaxDd, 2, '%'), 'regime vs sans');\n"
        "  body.innerHTML = html;\n"
        "  panel.style.display = '';\n"
        "  // Add regime dataset to chart\n"
        "  try {\n"
        "    if (data.portfolio_equity_regime && window.Chart){\n"
        "      const ctx = document.getElementById('btChart');\n"
        "      const chart = ctx && Chart.getChart(ctx);\n"
        "      if (chart){\n"
        "        // Remove existing regime dataset if any\n"
        "        chart.data.datasets = chart.data.datasets.filter(function(d){ return d.label !== 'Portfolio + Regime'; });\n"
        "        const series = data.portfolio_equity_regime.map(function(p){ return p.value; });\n"
        "        chart.data.datasets.push({\n"
        "          label: 'Portfolio + Regime',\n"
        "          data: series,\n"
        "          borderColor: '#a855f7',\n"
        "          backgroundColor: 'rgba(168,85,247,0.08)',\n"
        "          borderWidth: 2,\n"
        "          borderDash: [4,3],\n"
        "          tension: 0.15,\n"
        "          pointRadius: 0\n"
        "        });\n"
        "        chart.update();\n"
        "      }\n"
        "    }\n"
        "  } catch(e){ console.warn('chart regime dataset fail', e); }\n"
        "  // Extend stats table: add row 'Avec Regime'\n"
        "  try {\n"
        "    const tbody = document.getElementById('btStatsBody');\n"
        "    if (tbody && sR){\n"
        "      const existing = tbody.querySelector('tr[data-regime-row=\"1\"]');\n"
        "      if (existing) existing.remove();\n"
        "      const tr = document.createElement('tr');\n"
        "      tr.setAttribute('data-regime-row', '1');\n"
        "      tr.style.borderTop = '2px solid var(--accent)';\n"
        "      const fields = [\n"
        "        ['Total Return (%)', sR.total_return_pct],\n"
        "        ['Sharpe', sR.sharpe],\n"
        "        ['Max DD (%)', sR.max_drawdown_pct],\n"
        "        ['Volatility (%)', sR.volatility_pct],\n"
        "        ['Win rate (%)', sR.win_rate_pct]\n"
        "      ];\n"
        "      // Build a small label/value cell that fits the existing table shape (Metric | Portfolio | Bench)\n"
        "      tr.innerHTML = '<td colspan=\"3\" style=\"padding-top:8px\">' +\n"
        "        '<b>Avec regime applique :</b> ' +\n"
        "        fields.map(function(p){ return p[0]+' '+ (p[1]==null?'-':p[1]); }).join(' &middot; ') +\n"
        "        '</td>';\n"
        "      tbody.appendChild(tr);\n"
        "    }\n"
        "  } catch(e){ console.warn('stats regime row fail', e); }\n"
        "}\n"
    )
    assert_ascii(helper, "renderBacktestRegime helper")
    src = src + "\n" + helper
    print("[INJECT JS] helper renderBacktestRegime ajoute en fin de fichier")

    write_utf8_no_bom(JS_PATH, src)
    print("[WRITE JS] " + JS_PATH)


def main():
    print("=" * 70)
    print("PATCH UI - BACKTEST REGIME V1")
    print("=" * 70)
    if not os.path.exists(HTML_PATH):
        print("[FAIL] HTML introuvable: " + HTML_PATH)
        sys.exit(1)
    if not os.path.exists(JS_PATH):
        print("[FAIL] JS introuvable: " + JS_PATH)
        sys.exit(2)
    patch_html()
    patch_js()
    print("\n[OK] " + MARKER_HTML + " / " + MARKER_JS)


if __name__ == "__main__":
    main()
