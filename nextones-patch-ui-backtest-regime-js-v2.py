"""
[PATCH_UI_BACKTEST_REGIME_V2]
Patch JS ONLY : ajoute le support 'regime' dans runBacktest + renderBacktestResults.

Le patch v1 a echoue silencieusement sur le JS (HTML deja patche, JS marker absent).
La cause : la regex 'apiFetch(/api/backtest' matche d'abord dans le helper apiFetch
lui-meme (L460), pas dans le body de runBacktest (L5260).

V2 strategie :
  - Cherche dans une fenetre limitee APRES 'async function runBacktest()' UNIQUEMENT.
  - 3 injections distinctes a 3 ancres precis :
    A) declaration applyRegime apres 'async function runBacktest() {'
    B) ajoute body.apply_regime = applyRegime AVANT 'const resp = await apiFetch'
    C) insere appel renderBacktestRegime(data) AVANT le '}' final de renderBacktestResults
    D) append helper renderBacktestRegime() en fin de fichier
  - Approche basee sur line index plutot que regex globale.
  - Idempotent (marker check), backup .bak.<timestamp>.
ASCII pur strict (escape \\u00xx pour accents JS).
"""
import io
import os
import sys
import re
import shutil
import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
JS_PATH = os.path.join(ROOT, "app.js")
MARKER = "// [PATCH_UI_BACKTEST_REGIME_V2]"


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


def find_line(lines, predicate, start=0, end=None):
    """Return 0-based index of first line where predicate(line) is True."""
    if end is None:
        end = len(lines)
    for i in range(start, end):
        if predicate(lines[i]):
            return i
    return -1


def main():
    print("=" * 70)
    print("PATCH app.js - BACKTEST REGIME V2 (JS only, robuste)")
    print("=" * 70)

    if not os.path.exists(JS_PATH):
        print("[FAIL] introuvable: " + JS_PATH)
        sys.exit(1)

    src = read_utf8_sig(JS_PATH)
    if MARKER in src:
        print("[SKIP] marker deja present " + MARKER)
        return

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = JS_PATH + ".bak." + ts
    shutil.copy2(JS_PATH, bak)
    print("[BACKUP] " + bak)

    lines = src.splitlines(keepends=False)

    # -----------------------------------------------------------------
    # ANCHOR 1 : 'async function runBacktest() {' (ligne EXACTE)
    # -----------------------------------------------------------------
    idx_run = find_line(lines, lambda ln: ln.strip() == "async function runBacktest() {")
    if idx_run < 0:
        print("[FAIL] ancre 'async function runBacktest() {' introuvable")
        sys.exit(2)
    print("[ANCHOR-A] runBacktest L%d" % (idx_run + 1))

    # -----------------------------------------------------------------
    # ANCHOR 2 : entre runBacktest et le 'const resp = await apiFetch(' suivant,
    # le 'try {' et la ligne juste avant. On veut inserer body.apply_regime
    # avant 'try {' ou juste avant 'const resp = await apiFetch'.
    # -----------------------------------------------------------------
    # Cherche 'const resp = await apiFetch' dans la fenetre apres idx_run
    idx_resp = -1
    for j in range(idx_run, min(idx_run + 80, len(lines))):
        if "const resp = await apiFetch(" in lines[j] and "/api/backtest" in (lines[j] + lines[j + 1] if j + 1 < len(lines) else lines[j]):
            idx_resp = j
            break
    # fallback : verifie sur la ligne suivante aussi (multi-line)
    if idx_resp < 0:
        for j in range(idx_run, min(idx_run + 80, len(lines))):
            if "const resp = await apiFetch(" in lines[j]:
                idx_resp = j
                break
    if idx_resp < 0:
        print("[FAIL] 'const resp = await apiFetch(' introuvable dans runBacktest")
        sys.exit(3)
    print("[ANCHOR-B] const resp = await apiFetch L%d" % (idx_resp + 1))

    # Cherche aussi le 'try {' immediatement au-dessus
    idx_try = -1
    for j in range(idx_resp, idx_run, -1):
        if lines[j].strip() == "try {":
            idx_try = j
            break
    if idx_try < 0:
        print("[FAIL] ligne 'try {' avant const resp introuvable")
        sys.exit(4)
    print("[ANCHOR-C] try { L%d" % (idx_try + 1))

    # -----------------------------------------------------------------
    # ANCHOR 3 : function renderBacktestResults(data, benchTicker) { ... }
    # On cherche sa fermeture (premier '}' qui ferme la fonction par bracket match)
    # -----------------------------------------------------------------
    idx_render = find_line(lines, lambda ln: ln.startswith("function renderBacktestResults("))
    if idx_render < 0:
        print("[FAIL] function renderBacktestResults introuvable")
        sys.exit(5)
    print("[ANCHOR-D] renderBacktestResults L%d" % (idx_render + 1))

    # bracket match a partir du { de la signature
    sig_line = lines[idx_render]
    open_pos = sig_line.find("{")
    if open_pos < 0:
        print("[FAIL] '{' sur signature renderBacktestResults introuvable")
        sys.exit(6)

    depth = 1
    idx_render_close = -1
    j = idx_render
    col = open_pos + 1
    while j < len(lines):
        line = lines[j]
        # Scan caracteres
        start_col = 0 if j != idx_render else col
        # Tres simple, ignore les strings/regex/comments JS (heuristique acceptable
        # ici car le code ne contient pas d'accolades dans des strings sur ces blocs)
        for k in range(start_col, len(line)):
            c = line[k]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    idx_render_close = j
                    break
        if idx_render_close >= 0:
            break
        j += 1
    if idx_render_close < 0:
        print("[FAIL] fermeture renderBacktestResults introuvable par bracket-match")
        sys.exit(7)
    print("[ANCHOR-E] renderBacktestResults close L%d" % (idx_render_close + 1))

    # -----------------------------------------------------------------
    # INJECTIONS (par ordre DECROISSANT de ligne pour ne pas decaler les autres)
    # -----------------------------------------------------------------

    # Snippet 1 : declaration applyRegime juste apres 'async function runBacktest() {'
    snippet_decl = [
        "  " + MARKER,
        "  const applyRegime = (document.getElementById('btApplyRegime') && document.getElementById('btApplyRegime').checked) || false;",
    ]
    # Snippet 2 : body.apply_regime AVANT 'try {' (donc apres le dernier body.xxx ou apres la ligne juste avant 'try {')
    snippet_body = [
        "  " + MARKER,
        "  body.apply_regime = applyRegime;",
    ]
    # Snippet 3 : appel renderBacktestRegime AVANT la '}' qui ferme renderBacktestResults
    snippet_call = [
        "  " + MARKER,
        "  try { renderBacktestRegime(data); } catch(e) { console.warn('regime render fail', e); }",
    ]
    # Snippet 4 : helper en fin de fichier (escape \u00xx pour accents)
    helper_lines = [
        "",
        MARKER,
        "function renderBacktestRegime(data){",
        "  const panel = document.getElementById('btRegimePanel');",
        "  const body  = document.getElementById('btRegimeBody');",
        "  if (!panel || !body) return;",
        "  if (!data || !data.regime_summary){",
        "    panel.style.display = 'none';",
        "    return;",
        "  }",
        "  const s  = data.regime_summary || {};",
        "  const eq = s.equity || {calm_days:0, normal_days:0, stress_days:0};",
        "  const cr = s.crypto || {calm_days:0, normal_days:0, stress_days:0};",
        "  const sR = data.stats_regime || null;",
        "  const sB = data.stats || null;",
        "  let dSharpe = null, dMaxDd = null;",
        "  if (sR && sB){",
        "    dSharpe = (sR.sharpe||0) - (sB.sharpe||0);",
        "    dMaxDd  = (sR.max_drawdown_pct||0) - (sB.max_drawdown_pct||0);",
        "  }",
        "  function _kpi(label, value, sub){",
        "    return '<div style=\"background:var(--surface-2);padding:var(--space-3);border-radius:var(--radius-md)\">' +",
        "      '<div style=\"font-size:var(--text-xs);color:var(--text-muted)\">' + label + '</div>' +",
        "      '<div class=\"mono\" style=\"font-size:var(--text-lg);font-weight:600\">' + value + '</div>' +",
        "      (sub ? '<div style=\"font-size:var(--text-xs);color:var(--text-muted);margin-top:2px\">' + sub + '</div>' : '') +",
        "    '</div>';",
        "  }",
        "  function _fs(v, dp, suffix){",
        "    if (v === null || v === undefined || isNaN(v)) return '-';",
        "    const f = (Math.abs(v)).toFixed(dp);",
        "    return (v >= 0 ? '+' : '-') + f + (suffix||'');",
        "  }",
        "  const eqStr = 'CALM ' + eq.calm_days + ' / NORM ' + eq.normal_days + ' / STR ' + eq.stress_days;",
        "  const crStr = 'CALM ' + cr.calm_days + ' / NORM ' + cr.normal_days + ' / STR ' + cr.stress_days;",
        "  let html = '';",
        "  html += _kpi('Equity jours', eqStr, 'base ' + (s.base_equity_weight_pct||0).toFixed(1) + '%');",
        "  html += _kpi('Crypto jours', crStr, 'base ' + (s.base_crypto_weight_pct||0).toFixed(1) + '%');",
        "  html += _kpi('Delta Sharpe', _fs(dSharpe, 2, ''), 'regime vs sans');",
        "  html += _kpi('Delta Max DD', _fs(dMaxDd, 2, '%'), 'regime vs sans');",
        "  body.innerHTML = html;",
        "  panel.style.display = '';",
        "  // Add regime dataset to chart (Chart.js)",
        "  try {",
        "    if (data.portfolio_equity_regime && window.Chart){",
        "      const ctx = document.getElementById('btChart');",
        "      const chart = ctx && Chart.getChart(ctx);",
        "      if (chart){",
        "        chart.data.datasets = chart.data.datasets.filter(function(d){ return d.label !== 'Portfolio + Regime'; });",
        "        const series = data.portfolio_equity_regime.map(function(p){ return p.value; });",
        "        chart.data.datasets.push({",
        "          label: 'Portfolio + Regime',",
        "          data: series,",
        "          borderColor: '#a855f7',",
        "          backgroundColor: 'rgba(168,85,247,0.08)',",
        "          borderWidth: 2,",
        "          borderDash: [4,3],",
        "          tension: 0.15,",
        "          pointRadius: 0",
        "        });",
        "        chart.update();",
        "      }",
        "    }",
        "  } catch(e){ console.warn('chart regime dataset fail', e); }",
        "  // Add row to stats table",
        "  try {",
        "    const tbody = document.getElementById('btStatsBody');",
        "    if (tbody && sR){",
        "      const existing = tbody.querySelector('tr[data-regime-row=\"1\"]');",
        "      if (existing) existing.remove();",
        "      const tr = document.createElement('tr');",
        "      tr.setAttribute('data-regime-row', '1');",
        "      tr.style.borderTop = '2px solid var(--accent, #a855f7)';",
        "      const f = [",
        "        ['Total Return %', sR.total_return_pct],",
        "        ['Sharpe', sR.sharpe],",
        "        ['Max DD %', sR.max_drawdown_pct],",
        "        ['Volatility %', sR.volatility_pct],",
        "        ['Win Rate %', sR.win_rate_pct]",
        "      ];",
        "      tr.innerHTML = '<td colspan=\"3\" style=\"padding-top:8px\"><b>Avec regime applique :</b> ' +",
        "        f.map(function(p){ return p[0]+' '+(p[1]==null?'-':p[1]); }).join(' &middot; ') +",
        "        '</td>';",
        "      tbody.appendChild(tr);",
        "    }",
        "  } catch(e){ console.warn('stats regime row fail', e); }",
        "}",
        "",
    ]

    # Verifier ASCII pur sur tous les snippets injectes
    all_snippets = "\n".join(snippet_decl + snippet_body + snippet_call + helper_lines)
    assert_ascii(all_snippets, "JS injection snippets")

    # ---- Inject en ordre decroissant ----
    # 1) Helper en fin (pas de decalage)
    lines.extend(helper_lines)
    print("[INJECT] helper renderBacktestRegime ajoute en fin de fichier (+%d lignes)" % len(helper_lines))

    # 2) Appel renderBacktestRegime AVANT idx_render_close
    for k, ln in enumerate(snippet_call):
        lines.insert(idx_render_close + k, ln)
    print("[INJECT] appel renderBacktestRegime avant L%d (renderBacktestResults close)" % (idx_render_close + 1))

    # 3) body.apply_regime AVANT idx_try (qui n'a pas bouge car idx_try < idx_render_close)
    # MAIS attention : idx_render_close > idx_try, et on a deja insere snippet_call de longueur 2.
    # On reste avant idx_try qui est en dessous (>) de idx_try... non en fait idx_try < idx_render_close
    # donc l'insertion d'avant ne deplace pas idx_try. OK.
    for k, ln in enumerate(snippet_body):
        lines.insert(idx_try + k, ln)
    print("[INJECT] body.apply_regime avant try (L%d)" % (idx_try + 1))

    # 4) declaration applyRegime apres async function runBacktest() {
    # idx_run < idx_try, donc encore non deplace. On insere a idx_run + 1.
    for k, ln in enumerate(snippet_decl):
        lines.insert(idx_run + 1 + k, ln)
    print("[INJECT] declaration applyRegime apres L%d (runBacktest open)" % (idx_run + 1))

    new_src = "\n".join(lines) + "\n"

    # ---- VALIDATION JS basique : equilibre des accolades dans la fenetre runBacktest ----
    # Pas de parser JS dispo en stdlib, on verifie un equilibre brut dans l'ancre runBacktest
    fragment = "\n".join(lines[idx_run:idx_run + 90])
    op = fragment.count("{")
    cl = fragment.count("}")
    print("[VALIDATE] fragment runBacktest braces: open=%d, close=%d (delta=%d, attendu peut etre non nul)" % (op, cl, op - cl))

    # Ecrit tmp puis remplace
    tmp = JS_PATH + ".tmp"
    write_utf8_no_bom(tmp, new_src)
    os.replace(tmp, JS_PATH)
    print("[WRITE] %s (lignes totales: %d)" % (JS_PATH, len(lines)))
    print("[OK] " + MARKER)


if __name__ == "__main__":
    main()
