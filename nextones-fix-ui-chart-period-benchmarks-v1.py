#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[UI_CHART_PERIOD_BENCHMARKS_V1]

Phase 2 frontend : ajoute 4 boutons periode (30j/6m/1a/Tout) + 2 toggles
benchmark (SPY/QQQ) au-dessus du graphe portfolio. Tout est normalise en
performance base 100.

Patches :
  A) index.html : insere une barre de controles dans .chart-section,
     ajuste le titre.
  B) app.js : remplace loadPortfolioHistory() et renderPortfolioChart() par
     une version qui :
       - lit state.chartPeriod (defaut '30d') et state.chartBenchmarks (Set)
       - appelle /api/portfolio/history?period=...&benchmarks=...
       - trace 1 a 3 lignes (Portfolio + SPY + QQQ) en perf_base100
       - met a jour le titre dynamique
       - attache les listeners aux boutons/toggles

Idempotent (marker en commentaire), backups .bak.<timestamp>, validations
syntaxe HTML (presence anchor) et JS (presence anchor), zero ASCII non-pur.
"""
import os
import shutil
import sys
import time

INDEX = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html"
APPJS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

MARKER = "[UI_CHART_PERIOD_BENCHMARKS_V1]"

# ---------------------------------------------------------------- INDEX HTML

HTML_ANCHOR = (
    '      <!-- Portfolio chart -->\n'
    '      <div class="chart-section">\n'
    '        <div class="section-header">\n'
    '          <span class="section-title">Portfolio Value \xe2\x80\x94 30 Days</span>\n'
    '          <span class="text-muted" style="font-size: var(--text-xs); font-family: var(--font-mono); color: var(--color-text-faint)" id="chartUpdateLabel"></span>\n'
    '        </div>\n'
    '        <div class="chart-container" id="chartContainer">\n'
    '          <canvas id="portfolioChart"></canvas>\n'
    '        </div>\n'
    '      </div>\n'
)

HTML_REPLACEMENT = (
    '      <!-- Portfolio chart [UI_CHART_PERIOD_BENCHMARKS_V1] -->\n'
    '      <div class="chart-section">\n'
    '        <div class="section-header">\n'
    '          <span class="section-title" id="chartTitle">Portfolio \xe2\x80\x94 30 jours</span>\n'
    '          <span class="text-muted" style="font-size: var(--text-xs); font-family: var(--font-mono); color: var(--color-text-faint)" id="chartUpdateLabel"></span>\n'
    '        </div>\n'
    '        <div id="chartControls" style="display:flex;align-items:center;gap:var(--space-3);padding:var(--space-2) var(--space-4);border-bottom:1px solid var(--color-divider);flex-wrap:wrap">\n'
    '          <div style="display:flex;gap:4px" role="tablist" aria-label="Periode">\n'
    '            <button type="button" class="btn chart-period-btn is-active" data-period="30d" style="font-size:var(--text-xs);padding:3px 10px;border:1px solid var(--color-border);border-radius:var(--radius-sm);cursor:pointer;background:var(--color-surface-alt,rgba(255,255,255,0.04));color:var(--color-text)">30j</button>\n'
    '            <button type="button" class="btn chart-period-btn"           data-period="6m"  style="font-size:var(--text-xs);padding:3px 10px;border:1px solid var(--color-border);border-radius:var(--radius-sm);cursor:pointer;background:transparent;color:var(--color-text-muted)">6 mois</button>\n'
    '            <button type="button" class="btn chart-period-btn"           data-period="1y"  style="font-size:var(--text-xs);padding:3px 10px;border:1px solid var(--color-border);border-radius:var(--radius-sm);cursor:pointer;background:transparent;color:var(--color-text-muted)">1 an</button>\n'
    '            <button type="button" class="btn chart-period-btn"           data-period="all" style="font-size:var(--text-xs);padding:3px 10px;border:1px solid var(--color-border);border-radius:var(--radius-sm);cursor:pointer;background:transparent;color:var(--color-text-muted)">Depuis debut</button>\n'
    '          </div>\n'
    '          <div style="height:18px;width:1px;background:var(--color-divider)"></div>\n'
    '          <div style="display:flex;gap:8px;align-items:center;font-size:var(--text-xs);color:var(--color-text-muted)">\n'
    '            <span>Comparer&nbsp;:</span>\n'
    '            <label style="display:inline-flex;gap:4px;align-items:center;cursor:pointer">\n'
    '              <input type="checkbox" class="chart-bench-toggle" data-ticker="SPY" /> SPY\n'
    '            </label>\n'
    '            <label style="display:inline-flex;gap:4px;align-items:center;cursor:pointer">\n'
    '              <input type="checkbox" class="chart-bench-toggle" data-ticker="QQQ" /> QQQ\n'
    '            </label>\n'
    '          </div>\n'
    '        </div>\n'
    '        <div class="chart-container" id="chartContainer">\n'
    '          <canvas id="portfolioChart"></canvas>\n'
    '        </div>\n'
    '      </div>\n'
)

# Bytes containing the em-dash UTF-8 sequence (\xe2\x80\x94) -> we will encode the
# whole anchor/replacement to bytes for matching, since HTML is utf-8.


# ---------------------------------------------------------------- APP JS

JS_ANCHOR = (
    "async function loadPortfolioHistory() {\n"
    "  try {\n"
    "    const data = await apiFetch('/api/portfolio/history');\n"
    "    const history = data.history ?? data.data ?? data ?? [];\n"
    "    renderPortfolioChart(history);\n"
    "\n"
    "    const label = document.getElementById('chartUpdateLabel');\n"
    "    if (label) label.textContent = 'Updated ' + fmtDatetime(new Date().toISOString());\n"
    "  } catch (err) {\n"
    "    // Render chart with placeholder data\n"
    "    renderPortfolioChart(generatePlaceholderHistory());\n"
    "    document.getElementById('chartUpdateLabel').textContent = 'Live data unavailable';\n"
    "  }\n"
    "}\n"
)

JS_REPLACEMENT = (
    "// [UI_CHART_PERIOD_BENCHMARKS_V1]\n"
    "if (typeof state !== 'undefined') {\n"
    "  state.chartPeriod     = state.chartPeriod     || '30d';\n"
    "  state.chartBenchmarks = state.chartBenchmarks || new Set();\n"
    "}\n"
    "const CHART_PERIOD_LABEL = { '30d': '30 jours', '6m': '6 mois', '1y': '1 an', 'all': 'depuis le debut' };\n"
    "\n"
    "async function loadPortfolioHistory() {\n"
    "  try {\n"
    "    const period = (state && state.chartPeriod) || '30d';\n"
    "    const benchSet = (state && state.chartBenchmarks) || new Set();\n"
    "    const benchCsv = Array.from(benchSet).join(',');\n"
    "    const qs = '?period=' + encodeURIComponent(period) + (benchCsv ? '&benchmarks=' + encodeURIComponent(benchCsv) : '');\n"
    "    const data = await apiFetch('/api/portfolio/history' + qs);\n"
    "    const portfolio = data.portfolio || data.history || data.data || data || [];\n"
    "    const benchmarks = data.benchmarks || {};\n"
    "    renderPortfolioChart(portfolio, benchmarks);\n"
    "\n"
    "    const title = document.getElementById('chartTitle');\n"
    "    if (title) title.textContent = 'Portfolio \\u2014 ' + (CHART_PERIOD_LABEL[period] || period);\n"
    "    const label = document.getElementById('chartUpdateLabel');\n"
    "    if (label) label.textContent = 'Updated ' + fmtDatetime(new Date().toISOString());\n"
    "  } catch (err) {\n"
    "    renderPortfolioChart(generatePlaceholderHistory(), {});\n"
    "    const lbl = document.getElementById('chartUpdateLabel');\n"
    "    if (lbl) lbl.textContent = 'Live data unavailable';\n"
    "  }\n"
    "}\n"
    "\n"
    "function _normalizeBase100(arr, valueKey) {\n"
    "  if (!arr || !arr.length) return [];\n"
    "  const base = arr[0][valueKey] || 1;\n"
    "  return arr.map(d => ({ date: d.date, v: (d[valueKey] / base) * 100 }));\n"
    "}\n"
    "\n"
    "function _initChartControls() {\n"
    "  if (window.__chartControlsInit) return;\n"
    "  window.__chartControlsInit = true;\n"
    "  document.querySelectorAll('.chart-period-btn').forEach(btn => {\n"
    "    btn.addEventListener('click', () => {\n"
    "      const p = btn.getAttribute('data-period');\n"
    "      if (state) state.chartPeriod = p;\n"
    "      document.querySelectorAll('.chart-period-btn').forEach(b => {\n"
    "        const active = b === btn;\n"
    "        b.classList.toggle('is-active', active);\n"
    "        b.style.background = active ? 'var(--color-surface-alt,rgba(255,255,255,0.04))' : 'transparent';\n"
    "        b.style.color = active ? 'var(--color-text)' : 'var(--color-text-muted)';\n"
    "      });\n"
    "      loadPortfolioHistory();\n"
    "    });\n"
    "  });\n"
    "  document.querySelectorAll('.chart-bench-toggle').forEach(cb => {\n"
    "    cb.addEventListener('change', () => {\n"
    "      const t = cb.getAttribute('data-ticker');\n"
    "      if (!state) return;\n"
    "      if (!state.chartBenchmarks) state.chartBenchmarks = new Set();\n"
    "      if (cb.checked) state.chartBenchmarks.add(t); else state.chartBenchmarks.delete(t);\n"
    "      loadPortfolioHistory();\n"
    "    });\n"
    "  });\n"
    "}\n"
)

JS_RENDER_ANCHOR = (
    "function renderPortfolioChart(history) {\n"
    "  const colors = getChartColors();\n"
    "  const canvas = document.getElementById('portfolioChart');\n"
    "  if (!canvas) return;\n"
    "\n"
    "  const labels = history.map(d => {\n"
    "    const dateStr = d.date ?? d.timestamp ?? d.ts ?? '';\n"
    "    const date = new Date(dateStr);\n"
    "    return isNaN(date) ? dateStr : date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });\n"
    "  });\n"
    "  const values = history.map(d => d.total_value ?? d.value ?? d.portfolio_value ?? d.nav ?? 0);\n"
    "\n"
    "  if (state.portfolioChart) {\n"
    "    state.portfolioChart.destroy();\n"
    "  }\n"
    "\n"
    "  state.portfolioChart = new Chart(canvas, {\n"
    "    type: 'line',\n"
    "    data: {\n"
    "      labels,\n"
    "      datasets: [{\n"
    "        label: 'Portfolio Value',\n"
    "        data: values,\n"
    "        borderColor: colors.primary,\n"
    "        backgroundColor: colors.primaryAlpha,\n"
    "        borderWidth: 1.5,\n"
    "        tension: 0.3,\n"
    "        fill: true,\n"
    "        pointRadius: 0,\n"
    "        pointHoverRadius: 4,\n"
    "        pointBorderColor: colors.primary,\n"
    "        pointBackgroundColor: colors.primary,\n"
    "      }],\n"
    "    },\n"
    "    options: {\n"
    "      responsive: true,\n"
    "      maintainAspectRatio: false,\n"
    "      animation: { duration: 400, easing: 'easeInOutQuart' },\n"
    "      interaction: { mode: 'index', intersect: false },\n"
    "      plugins: {\n"
    "        legend: { display: false },\n"
    "        tooltip: {\n"
    "          backgroundColor: '#1c1c1b',\n"
    "          titleColor: '#706f6d',\n"
    "          bodyColor: '#c8c7c5',\n"
    "          borderColor: '#302f2d',\n"
    "          borderWidth: 1,\n"
    "          padding: 10,\n"
    "          callbacks: {\n"
    "            label: (ctx) => ' ' + fmtUSDCompact(ctx.parsed.y),\n"
    "          },\n"
    "        },\n"
    "      },\n"
    "      scales: {\n"
    "        x: {\n"
    "          grid: { color: colors.grid, drawBorder: false },\n"
    "          ticks: {\n"
    "            color: colors.tick,\n"
    "            font: { family: \"'JetBrains Mono', monospace\", size: 10 },\n"
    "            maxTicksLimit: 8,\n"
    "            maxRotation: 0,\n"
    "          },\n"
    "        },\n"
    "        y: {\n"
    "          position: 'right',\n"
    "          grid: { color: colors.grid, drawBorder: false },\n"
    "          ticks: {\n"
    "            color: colors.tick,\n"
    "            font: { family: \"'JetBrains Mono', monospace\", size: 10 },\n"
    "            callback: (val) => fmtUSDCompact(val),\n"
    "          },\n"
    "        },\n"
    "      },\n"
    "    },\n"
    "  });\n"
    "}\n"
)

JS_RENDER_REPLACEMENT = (
    "function renderPortfolioChart(history, benchmarks) {\n"
    "  const colors = getChartColors();\n"
    "  const canvas = document.getElementById('portfolioChart');\n"
    "  if (!canvas) return;\n"
    "  benchmarks = benchmarks || {};\n"
    "\n"
    "  // Master labels = portfolio dates\n"
    "  const labels = history.map(d => {\n"
    "    const dateStr = d.date || d.timestamp || d.ts || '';\n"
    "    const dt = new Date(dateStr);\n"
    "    return isNaN(dt) ? dateStr : dt.toLocaleDateString('fr-FR', { month: 'short', day: 'numeric' });\n"
    "  });\n"
    "\n"
    "  // Portfolio in base 100\n"
    "  const pfValues = history.map(d => {\n"
    "    if (typeof d.perf_base100 === 'number') return d.perf_base100;\n"
    "    return d.total_value || d.value || d.nav || 0;\n"
    "  });\n"
    "  // If raw values, normalize ourselves\n"
    "  let pfNorm = pfValues;\n"
    "  if (pfValues.length && pfValues[0] !== 100 && !history[0].perf_base100) {\n"
    "    const base = pfValues[0] || 1;\n"
    "    pfNorm = pfValues.map(v => (v / base) * 100);\n"
    "  }\n"
    "\n"
    "  const datasets = [{\n"
    "    label: 'Portfolio',\n"
    "    data: pfNorm,\n"
    "    borderColor: colors.primary,\n"
    "    backgroundColor: colors.primaryAlpha,\n"
    "    borderWidth: 1.8,\n"
    "    tension: 0.25,\n"
    "    fill: true,\n"
    "    pointRadius: 0,\n"
    "    pointHoverRadius: 4,\n"
    "  }];\n"
    "\n"
    "  // Align benchmark series on the portfolio's date axis\n"
    "  // (forward-fill missing dates via last-known value).\n"
    "  const BENCH_COLORS = { SPY: '#3498db', QQQ: '#9b59b6' };\n"
    "  Object.keys(benchmarks).forEach(tk => {\n"
    "    const series = benchmarks[tk] || [];\n"
    "    if (!series.length) return;\n"
    "    const byDate = {};\n"
    "    series.forEach(s => { byDate[s.date] = (typeof s.perf_base100 === 'number') ? s.perf_base100 : null; });\n"
    "    let last = null;\n"
    "    const aligned = history.map(d => {\n"
    "      const k = d.date;\n"
    "      if (byDate[k] != null) { last = byDate[k]; }\n"
    "      return last;\n"
    "    });\n"
    "    datasets.push({\n"
    "      label: tk,\n"
    "      data: aligned,\n"
    "      borderColor: BENCH_COLORS[tk] || '#888',\n"
    "      backgroundColor: 'transparent',\n"
    "      borderWidth: 1.4,\n"
    "      borderDash: [4, 3],\n"
    "      tension: 0.25,\n"
    "      fill: false,\n"
    "      pointRadius: 0,\n"
    "      pointHoverRadius: 4,\n"
    "    });\n"
    "  });\n"
    "\n"
    "  if (state.portfolioChart) {\n"
    "    state.portfolioChart.destroy();\n"
    "  }\n"
    "\n"
    "  state.portfolioChart = new Chart(canvas, {\n"
    "    type: 'line',\n"
    "    data: { labels, datasets },\n"
    "    options: {\n"
    "      responsive: true,\n"
    "      maintainAspectRatio: false,\n"
    "      animation: { duration: 400, easing: 'easeInOutQuart' },\n"
    "      interaction: { mode: 'index', intersect: false },\n"
    "      plugins: {\n"
    "        legend: {\n"
    "          display: datasets.length > 1,\n"
    "          position: 'top',\n"
    "          align: 'end',\n"
    "          labels: { color: colors.tick, font: { family: \"'JetBrains Mono', monospace\", size: 10 }, boxWidth: 10 },\n"
    "        },\n"
    "        tooltip: {\n"
    "          backgroundColor: '#1c1c1b',\n"
    "          titleColor: '#706f6d',\n"
    "          bodyColor: '#c8c7c5',\n"
    "          borderColor: '#302f2d',\n"
    "          borderWidth: 1,\n"
    "          padding: 10,\n"
    "          callbacks: {\n"
    "            label: (ctx) => {\n"
    "              const v = ctx.parsed.y;\n"
    "              if (v == null) return ctx.dataset.label + ' : -';\n"
    "              const perf = (v - 100).toFixed(2);\n"
    "              const sign = perf >= 0 ? '+' : '';\n"
    "              return ctx.dataset.label + ' : ' + v.toFixed(2) + '  (' + sign + perf + '%)';\n"
    "            },\n"
    "          },\n"
    "        },\n"
    "      },\n"
    "      scales: {\n"
    "        x: {\n"
    "          grid: { color: colors.grid, drawBorder: false },\n"
    "          ticks: {\n"
    "            color: colors.tick,\n"
    "            font: { family: \"'JetBrains Mono', monospace\", size: 10 },\n"
    "            maxTicksLimit: 8,\n"
    "            maxRotation: 0,\n"
    "          },\n"
    "        },\n"
    "        y: {\n"
    "          position: 'right',\n"
    "          grid: { color: colors.grid, drawBorder: false },\n"
    "          ticks: {\n"
    "            color: colors.tick,\n"
    "            font: { family: \"'JetBrains Mono', monospace\", size: 10 },\n"
    "            callback: (val) => Number(val).toFixed(0),\n"
    "          },\n"
    "        },\n"
    "      },\n"
    "    },\n"
    "  });\n"
    "\n"
    "  _initChartControls();\n"
    "}\n"
)


# ---------------------------------------------------------------- IO helpers

def read_bytes(path):
    with open(path, "rb") as f:
        data = f.read()
    return data


def write_bytes(path, data):
    with open(path, "wb") as f:
        f.write(data)


def backup(path):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bp = path + ".bak." + ts
    shutil.copy2(path, bp)
    return bp


# ---------------------------------------------------------------- main

def patch_html():
    raw = read_bytes(INDEX)
    bom = b""
    if raw.startswith(b"\xef\xbb\xbf"):
        bom = b"\xef\xbb\xbf"
        raw = raw[3:]

    marker_bytes = MARKER.encode("ascii")
    if marker_bytes in raw:
        print("HTML: marker already present, SKIP")
        return False

    anchor_b = HTML_ANCHOR.encode("latin-1")  # contains raw bytes \xe2\x80\x94
    repl_b = HTML_REPLACEMENT.encode("latin-1")

    count = raw.count(anchor_b)
    if count == 0:
        print("HTML: anchor not found")
        # Diagnose : try without em-dash
        no_dash = anchor_b.replace(b"\xe2\x80\x94", b"-")
        print("  raw em-dash bytes present in file: " + str(b"\xe2\x80\x94" in raw))
        sys.exit(10)
    if count > 1:
        print("HTML: anchor not unique, " + str(count))
        sys.exit(11)

    bp = backup(INDEX)
    print("HTML backup: " + bp)
    new_raw = raw.replace(anchor_b, repl_b, 1)
    write_bytes(INDEX, bom + new_raw)
    print("HTML WRITE OK")
    return True


def patch_js():
    raw = read_bytes(APPJS)
    bom = b""
    if raw.startswith(b"\xef\xbb\xbf"):
        bom = b"\xef\xbb\xbf"
        raw = raw[3:]

    if MARKER.encode("ascii") in raw:
        print("JS: marker already present, SKIP")
        return False

    anchor1 = JS_ANCHOR.encode("ascii")
    repl1 = JS_REPLACEMENT.encode("ascii")
    anchor2 = JS_RENDER_ANCHOR.encode("ascii")
    repl2 = JS_RENDER_REPLACEMENT.encode("ascii")

    c1 = raw.count(anchor1)
    c2 = raw.count(anchor2)
    if c1 == 0:
        print("JS: anchor #1 (loadPortfolioHistory) not found")
        sys.exit(20)
    if c1 > 1:
        print("JS: anchor #1 not unique, " + str(c1))
        sys.exit(21)
    if c2 == 0:
        print("JS: anchor #2 (renderPortfolioChart) not found")
        sys.exit(22)
    if c2 > 1:
        print("JS: anchor #2 not unique, " + str(c2))
        sys.exit(23)

    bp = backup(APPJS)
    print("JS backup: " + bp)

    new_raw = raw.replace(anchor1, repl1, 1).replace(anchor2, repl2, 1)
    write_bytes(APPJS, bom + new_raw)
    print("JS WRITE OK")
    return True


def main():
    if not os.path.isfile(INDEX):
        print("ERROR: index.html not found")
        sys.exit(2)
    if not os.path.isfile(APPJS):
        print("ERROR: app.js not found")
        sys.exit(3)

    h = patch_html()
    j = patch_js()

    if h or j:
        print("DONE " + MARKER)
    else:
        print("ALREADY APPLIED " + MARKER)


if __name__ == "__main__":
    main()
