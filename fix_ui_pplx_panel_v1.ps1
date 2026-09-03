# [FIX_UI_PPLX_PANEL_V1] Ajoute le panel "Perplexity Insights" dans index.html + app.js
# Strategie :
#   - Detecte un point d'insertion dans index.html (juste avant </main> ou </body>)
#   - Ajoute un <section id="pplx-insights-panel"> auto-rafraichi
#   - Patche app.js avec fetchPplxSnapshot() + renderPplxPanel()
# Marqueurs : [PPLX_PANEL_V1_HTML] et [PPLX_PANEL_V1_JS]
$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$html = Join-Path $root "index.html"
$js   = Join-Path $root "app.js"

if (-not (Test-Path $html)) { Write-Host "[ERR] $html introuvable" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $js))   { Write-Host "[ERR] $js introuvable" -ForegroundColor Red; exit 1 }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
Copy-Item $html "$html.bak_pplxpanel_$stamp" -Force
Copy-Item $js   "$js.bak_pplxpanel_$stamp"   -Force
Write-Host "[BACKUP] index.html.bak_pplxpanel_$stamp" -ForegroundColor Cyan
Write-Host "[BACKUP] app.js.bak_pplxpanel_$stamp"   -ForegroundColor Cyan

$helper = Join-Path $env:TEMP "ui_pplx_patch_$(Get-Random).py"
$helperCode = @'
import re, sys
from pathlib import Path

html_path = Path(sys.argv[1])
js_path = Path(sys.argv[2])

# ---------------------------------------------------------------------------
# 1. HTML
# ---------------------------------------------------------------------------
HTML_MARKER = "[PPLX_PANEL_V1_HTML]"
html = html_path.read_text(encoding="utf-8-sig")

if HTML_MARKER in html:
    print(f"[SKIP-HTML] {HTML_MARKER} deja present")
else:
    panel = '''
<!-- ''' + HTML_MARKER + ''' Panel Perplexity Insights -->
<section id="pplx-insights-panel" class="card" style="margin:20px 0;padding:16px;background:#fafafa;border:1px solid #e0e0e0;border-radius:8px;">
  <header style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <h2 style="margin:0;font-size:18px;color:#222;">Perplexity Insights</h2>
    <div style="display:flex;gap:8px;align-items:center;">
      <span id="pplx-snapshot-age" style="font-size:12px;color:#666;">-</span>
      <button id="pplx-refresh-btn" type="button" style="font-size:12px;padding:4px 10px;border:1px solid #1976d2;background:#fff;color:#1976d2;border-radius:4px;cursor:pointer;">Rafraichir</button>
    </div>
  </header>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
    <div>
      <h3 style="margin:0 0 8px 0;font-size:14px;color:#444;">Crypto (CryptoAgent)</h3>
      <table id="pplx-crypto-table" style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;">
        <thead>
          <tr style="background:#f0f0f0;text-align:left;">
            <th style="padding:6px;border-bottom:1px solid #ddd;">Ticker</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">Score</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">Sentiment</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">Age</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>

    <div>
      <h3 style="margin:0 0 8px 0;font-size:14px;color:#444;">Equity Quality (FactorAgent)</h3>
      <table id="pplx-equity-table" style="width:100%;border-collapse:collapse;font-size:13px;background:#fff;">
        <thead>
          <tr style="background:#f0f0f0;text-align:left;">
            <th style="padding:6px;border-bottom:1px solid #ddd;">Ticker</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">Qualite</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">Moat</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">RF</th>
            <th style="padding:6px;border-bottom:1px solid #ddd;">Age</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div id="pplx-detail-panel" style="margin-top:12px;padding:12px;background:#fff;border:1px solid #e0e0e0;border-radius:4px;display:none;">
    <button id="pplx-detail-close" type="button" style="float:right;border:none;background:none;cursor:pointer;font-size:16px;color:#999;">x</button>
    <div id="pplx-detail-content"></div>
  </div>

  <footer id="pplx-audit-line" style="margin-top:10px;padding-top:8px;border-top:1px solid #eee;font-size:11px;color:#888;">-</footer>
</section>
'''
    # Insertion juste avant </body>
    if "</body>" in html:
        html = html.replace("</body>", panel + "\n</body>", 1)
    else:
        html = html.rstrip() + panel
    html_path.write_text(html, encoding="utf-8")
    print(f"[OK-HTML] {HTML_MARKER} ajoute (panel + 2 tables + detail)")

# ---------------------------------------------------------------------------
# 2. JS
# ---------------------------------------------------------------------------
JS_MARKER = "[PPLX_PANEL_V1_JS]"
js = js_path.read_text(encoding="utf-8-sig")

if JS_MARKER in js:
    print(f"[SKIP-JS] {JS_MARKER} deja present")
else:
    js_block = '''

// ''' + JS_MARKER + ''' Logique du panel Perplexity Insights
(function() {
  function fmtAge(h) {
    if (h === null || h === undefined) return "-";
    if (h < 1) return Math.round(h * 60) + "min";
    if (h < 24) return h.toFixed(1) + "h";
    return Math.round(h / 24) + "j";
  }

  function badge(text, color) {
    return '<span style="display:inline-block;padding:2px 6px;border-radius:3px;background:' + color + ';color:#fff;font-size:11px;">' + text + '</span>';
  }

  function sentimentColor(s) {
    if (s === "bullish") return "#2e7d32";
    if (s === "bearish") return "#c62828";
    return "#757575";
  }

  function moatColor(m) {
    if (m === "wide") return "#1565c0";
    if (m === "narrow") return "#fb8c00";
    if (m === "none") return "#c62828";
    return "#757575";
  }

  function qualityColor(q) {
    if (q >= 85) return "#2e7d32";
    if (q >= 70) return "#1976d2";
    if (q >= 55) return "#fb8c00";
    return "#c62828";
  }

  async function fetchPplxSnapshot() {
    try {
      const r = await fetch("/api/pplx/cycle-snapshot");
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    } catch (e) {
      console.error("[PPLX] snapshot fetch failed", e);
      return null;
    }
  }

  async function fetchPplxDetail(kind, ticker) {
    const url = kind === "crypto" ? "/api/pplx/crypto/" + ticker : "/api/pplx/quality/" + ticker;
    try {
      const r = await fetch(url);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return await r.json();
    } catch (e) {
      return null;
    }
  }

  function renderDetail(kind, ticker, d) {
    const el = document.getElementById("pplx-detail-content");
    if (!el || !d) return;
    let html = '<h4 style="margin:0 0 8px 0;">' + ticker + ' (' + kind + ')</h4>';
    if (kind === "crypto") {
      html += '<p><strong>Score narratif:</strong> ' + d.narrative_score + '/100  ';
      html += badge(d.sentiment, sentimentColor(d.sentiment)) + '</p>';
      if (d.narratives) {
        const arr = Array.isArray(d.narratives) ? d.narratives : [d.narratives];
        html += '<p><strong>Narratifs:</strong></p><ul>';
        arr.forEach(n => { html += '<li>' + (n || '') + '</li>'; });
        html += '</ul>';
      }
      if (d.trading_thesis) html += '<p><strong>These trading:</strong> ' + d.trading_thesis + '</p>';
    } else {
      html += '<p><strong>Qualite:</strong> ' + d.quality_score + '/100  ' + badge(d.moat_strength || '-', moatColor(d.moat_strength)) + '</p>';
      html += '<p><strong>Earnings:</strong> ' + (d.earnings_trend || '-') + ' &nbsp; <strong>Management:</strong> ' + (d.management_quality || '-') + ' &nbsp; <strong>Bilan:</strong> ' + (d.balance_sheet_health || '-') + '</p>';
      if (d.red_flags && d.red_flags.length > 0) {
        html += '<p><strong style="color:#c62828;">Red flags (' + d.red_flags.length + '):</strong></p><ul>';
        d.red_flags.forEach(rf => { html += '<li style="color:#c62828;">' + rf + '</li>'; });
        html += '</ul>';
      }
      if (d.positive_catalysts && d.positive_catalysts.length > 0) {
        html += '<p><strong style="color:#2e7d32;">Catalysts:</strong></p><ul>';
        d.positive_catalysts.forEach(pc => { html += '<li style="color:#2e7d32;">' + pc + '</li>'; });
        html += '</ul>';
      }
      if (d.rationale) html += '<p><em>' + d.rationale + '</em></p>';
    }
    if (d.citations && d.citations.length > 0) {
      html += '<p><strong>Sources (' + d.citations.length + '):</strong><br>';
      d.citations.forEach((c, i) => {
        const url = typeof c === "string" ? c : (c.url || c);
        html += '<a href="' + url + '" target="_blank" rel="noopener" style="font-size:11px;color:#1976d2;margin-right:8px;">[' + (i+1) + ']</a>';
      });
      html += '</p>';
    }
    el.innerHTML = html;
    document.getElementById("pplx-detail-panel").style.display = "block";
  }

  function renderPplxPanel(snap) {
    if (!snap) return;
    document.getElementById("pplx-snapshot-age").textContent = "Maj: " + snap.generated_at;

    const cBody = document.querySelector("#pplx-crypto-table tbody");
    if (cBody) {
      cBody.innerHTML = "";
      (snap.crypto || []).forEach(c => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        tr.innerHTML = '<td style="padding:6px;border-bottom:1px solid #eee;"><strong>' + c.ticker + '</strong></td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;">' + (c.narrative_score?.toFixed(0) || '-') + '</td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;">' + badge(c.sentiment, sentimentColor(c.sentiment)) + '</td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;color:#888;">' + fmtAge(c.age_hours) + '</td>';
        tr.addEventListener("click", async () => {
          const d = await fetchPplxDetail("crypto", c.ticker);
          renderDetail("crypto", c.ticker, d);
        });
        cBody.appendChild(tr);
      });
    }

    const eBody = document.querySelector("#pplx-equity-table tbody");
    if (eBody) {
      eBody.innerHTML = "";
      (snap.equity || []).forEach(e => {
        const tr = document.createElement("tr");
        tr.style.cursor = "pointer";
        const rfBadge = e.red_flags_count > 0
          ? badge(e.red_flags_count, "#c62828")
          : '<span style="color:#999;font-size:11px;">0</span>';
        tr.innerHTML = '<td style="padding:6px;border-bottom:1px solid #eee;"><strong>' + e.ticker + '</strong></td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;"><span style="color:' + qualityColor(e.quality_score) + ';font-weight:bold;">' + (e.quality_score?.toFixed(0) || '-') + '</span></td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;">' + badge(e.moat_strength || '-', moatColor(e.moat_strength)) + '</td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;">' + rfBadge + '</td>' +
                       '<td style="padding:6px;border-bottom:1px solid #eee;color:#888;">' + fmtAge(e.age_hours) + '</td>';
        tr.addEventListener("click", async () => {
          const d = await fetchPplxDetail("equity", e.ticker);
          renderDetail("equity", e.ticker, d);
        });
        eBody.appendChild(tr);
      });
    }

    const audit = document.getElementById("pplx-audit-line");
    if (audit && snap.audit) {
      const parts = snap.audit.map(a => {
        const cost = (a.cost_usd_total || 0).toFixed ? a.cost_usd_total.toFixed(4) : (a.cost_usd_total || 0);
        return a.agent + " " + a.calls + " calls / $" + cost;
      });
      audit.textContent = "Audit Perplexity: " + parts.join(" | ");
    }
  }

  async function refreshPplxPanel() {
    const snap = await fetchPplxSnapshot();
    renderPplxPanel(snap);
  }

  document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("pplx-refresh-btn");
    if (btn) btn.addEventListener("click", refreshPplxPanel);
    const closeBtn = document.getElementById("pplx-detail-close");
    if (closeBtn) closeBtn.addEventListener("click", () => {
      document.getElementById("pplx-detail-panel").style.display = "none";
    });
    refreshPplxPanel();
    // Auto-refresh toutes les 5 minutes
    setInterval(refreshPplxPanel, 5 * 60 * 1000);
  });

  window.refreshPplxPanel = refreshPplxPanel;
})();
'''
    js = js.rstrip() + "\n" + js_block + "\n"
    js_path.write_text(js, encoding="utf-8")
    print(f"[OK-JS] {JS_MARKER} ajoute (logique panel + auto-refresh 5min)")

print("[DONE]")
'@

Set-Content -Path $helper -Value $helperCode -Encoding UTF8
py -3.13 $helper $html $js
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ROLLBACK]" -ForegroundColor Yellow
    Copy-Item "$html.bak_pplxpanel_$stamp" $html -Force
    Copy-Item "$js.bak_pplxpanel_$stamp"   $js   -Force
    Remove-Item $helper -Force -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}
Remove-Item $helper -Force -ErrorAction SilentlyContinue
Write-Host "[DONE] Panel Perplexity Insights actif (recharge F5)." -ForegroundColor Green
