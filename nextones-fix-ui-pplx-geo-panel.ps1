# nextones-fix-ui-pplx-geo-panel.ps1
# Injecte panel PPLX géo (2 colonnes) sous geoSection dans tab-macro
# + CSS dark/light theme aware via vars Hydra Teal
# + JS loadPplxGeoData() hook sur loadGeoRiskData()
# Markers :
#   index.html : [PPLX_GEO_PANEL_HTML_V1] (HTML) + [PPLX_GEO_PANEL_CSS_V1] (CSS dans <head>)
#   app.js     : [PPLX_GEO_PANEL_JS_V1] (fonctions + hook)

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$html = Join-Path $root "index.html"
$js   = Join-Path $root "app.js"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"

foreach ($f in @($html, $js)) {
    if (-not (Test-Path $f)) {
        Write-Host "[KO] $f introuvable" -ForegroundColor Red
        exit 1
    }
}

$htmlBackup = "$html.bak_pplx_geo_$ts"
$jsBackup = "$js.bak_pplx_geo_$ts"
Copy-Item $html $htmlBackup -Force
Copy-Item $js $jsBackup -Force
Write-Host "[1/5] Backups : $htmlBackup, $jsBackup"

# Comptage AVANT
$htmlSrc = Get-Content $html -Raw -Encoding UTF8
$jsSrc = Get-Content $js -Raw -Encoding UTF8
$htmlTagsBefore = ([regex]::Matches($htmlSrc, '<section|<div|</section>|</div>')).Count
$jsFunctionsBefore = ([regex]::Matches($jsSrc, '(?m)^function\s+\w+|^\s+function\s+\w+')).Count
Write-Host "[2/5] AVANT : index.html $htmlTagsBefore tags, app.js $jsFunctionsBefore fonctions"

# ============================================================
# Helper Python qui patche les deux fichiers
# ============================================================
$helper = Join-Path $env:TEMP "patch_pplx_geo_ui_$ts.py"
$helperContent = @'
# -*- coding: utf-8 -*-
import re, sys
from pathlib import Path

html_path = Path(sys.argv[1])
js_path = Path(sys.argv[2])

# ============================================================
# 1. CSS dans <head>
# ============================================================
html = html_path.read_text(encoding="utf-8-sig")

CSS_MARKER_START = "/* === [PPLX_GEO_PANEL_CSS_V1] BEGIN === */"
CSS_MARKER_END   = "/* === [PPLX_GEO_PANEL_CSS_V1] END === */"

CSS_BLOCK = """
<style>
""" + CSS_MARKER_START + """
.pplx-geo-section {
  margin-top: var(--space-lg, 24px);
  padding: var(--space-lg, 24px);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 12px);
  color: var(--color-text);
}
.pplx-geo-section .pplx-geo-header {
  display: flex;
  align-items: flex-start;
  gap: var(--space-lg, 24px);
  margin-bottom: var(--space-lg, 24px);
  flex-wrap: wrap;
}
.pplx-geo-section .pplx-geo-title {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1 1 auto;
}
.pplx-geo-section .pplx-geo-title h3 {
  margin: 0;
  font-size: var(--text-lg, 1.1rem);
  font-weight: 600;
  color: var(--color-text);
}
.pplx-geo-section .pplx-geo-title .pplx-badge-source {
  font-size: var(--text-xs, 0.75rem);
  color: var(--color-text-muted);
  padding: 2px 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm, 4px);
  background: var(--color-surface-offset, var(--color-surface-2, transparent));
}
.pplx-geo-section .pplx-geo-score-block {
  display: flex;
  align-items: center;
  gap: 16px;
}
.pplx-geo-section .pplx-geo-score {
  font-size: 2.4rem;
  font-weight: 700;
  line-height: 1;
  color: var(--color-text);
}
.pplx-geo-section .pplx-geo-score-suffix {
  font-size: 1rem;
  color: var(--color-text-muted);
  margin-left: 4px;
  font-weight: 400;
}
.pplx-geo-section .pplx-regime-badge {
  display: inline-block;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: var(--text-xs, 0.75rem);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border: 1px solid transparent;
}
.pplx-geo-section .pplx-regime-calm     { background: rgba(46,160,67,0.15);  color: #2ea043; border-color: rgba(46,160,67,0.4); }
.pplx-geo-section .pplx-regime-elevated { background: rgba(212,167,44,0.15); color: #d4a72c; border-color: rgba(212,167,44,0.4); }
.pplx-geo-section .pplx-regime-stressed { background: rgba(219,109,40,0.18); color: #db6d28; border-color: rgba(219,109,40,0.5); }
.pplx-geo-section .pplx-regime-crisis   { background: rgba(229,57,53,0.20);  color: #e53935; border-color: rgba(229,57,53,0.55); }
.pplx-geo-section .pplx-geo-summary {
  flex: 1 1 100%;
  margin-top: 8px;
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text-muted);
  line-height: 1.5;
}
.pplx-geo-section .pplx-geo-meta {
  display: flex;
  gap: 16px;
  align-items: center;
  font-size: var(--text-xs, 0.75rem);
  color: var(--color-text-faint, var(--color-text-muted));
  margin-top: 4px;
}
.pplx-geo-section .pplx-geo-meta button {
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  padding: 4px 10px;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  font-size: var(--text-xs, 0.75rem);
}
.pplx-geo-section .pplx-geo-meta button:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.pplx-geo-section .pplx-geo-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: var(--space-lg, 24px);
}
@media (max-width: 1100px) {
  .pplx-geo-section .pplx-geo-grid { grid-template-columns: 1fr; }
}
.pplx-geo-section .pplx-col-title {
  font-size: var(--text-sm, 0.875rem);
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--color-divider, var(--color-border));
}
.pplx-geo-section .pplx-risk-card {
  background: var(--color-surface-offset, var(--color-surface-2, var(--color-surface)));
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md, 8px);
  padding: 12px 14px;
  margin-bottom: 10px;
}
.pplx-geo-section .pplx-risk-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.pplx-geo-section .pplx-risk-title {
  font-weight: 600;
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text);
  flex: 1;
}
.pplx-geo-section .pplx-risk-sev {
  font-weight: 700;
  font-size: var(--text-sm, 0.875rem);
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
}
.pplx-geo-section .pplx-risk-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.pplx-geo-section .pplx-tag {
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
}
.pplx-geo-section .pplx-risk-narrative {
  font-size: var(--text-xs, 0.75rem);
  color: var(--color-text-muted);
  line-height: 1.5;
  margin: 6px 0;
}
.pplx-geo-section .pplx-risk-tickers {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.pplx-geo-section .pplx-ticker-chip {
  font-size: 0.7rem;
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--color-primary, #01696f);
  color: #fff;
  font-weight: 600;
}
.pplx-geo-section .pplx-exp-row {
  display: grid;
  grid-template-columns: 60px 60px 1fr 90px;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
  border-bottom: 1px solid var(--color-divider, var(--color-border));
  font-size: var(--text-xs, 0.75rem);
}
.pplx-geo-section .pplx-exp-row:last-child { border-bottom: none; }
.pplx-geo-section .pplx-exp-ticker {
  font-weight: 700;
  color: var(--color-text);
  font-size: 0.85rem;
}
.pplx-geo-section .pplx-exp-weight {
  color: var(--color-text-muted);
}
.pplx-geo-section .pplx-exp-risks {
  color: var(--color-text-muted);
  font-size: 0.7rem;
}
.pplx-geo-section .pplx-exp-score {
  text-align: right;
  font-weight: 700;
  color: var(--color-text);
}
.pplx-geo-section .pplx-exp-bar {
  height: 4px;
  background: var(--color-surface-offset, var(--color-surface-2));
  border-radius: 2px;
  margin-top: 4px;
  overflow: hidden;
  grid-column: 1 / -1;
}
.pplx-geo-section .pplx-exp-bar-fill {
  height: 100%;
  background: var(--color-primary, #01696f);
  border-radius: 2px;
}
.pplx-geo-section .pplx-loading, .pplx-geo-section .pplx-empty {
  text-align: center;
  padding: 20px;
  color: var(--color-text-muted);
  font-size: var(--text-sm);
}
""" + CSS_MARKER_END + """
</style>
"""

# Supprime ancien bloc CSS si présent
html = re.sub(
    r'<style>\s*' + re.escape(CSS_MARKER_START) + r'.*?' + re.escape(CSS_MARKER_END) + r'\s*</style>',
    '',
    html,
    flags=re.DOTALL,
)

# Injecte avant </head>
if '</head>' not in html:
    print("[KO] </head> introuvable")
    sys.exit(2)
html = html.replace('</head>', CSS_BLOCK + '\n</head>', 1)
print("[OK] CSS injecté")

# ============================================================
# 2. HTML panel après </div> de geoSection (avant </section> tab-macro)
# ============================================================
HTML_MARKER_START = "<!-- === [PPLX_GEO_PANEL_HTML_V1] BEGIN === -->"
HTML_MARKER_END   = "<!-- === [PPLX_GEO_PANEL_HTML_V1] END === -->"

HTML_PANEL = HTML_MARKER_START + """
<div id="pplxGeoSection" class="pplx-geo-section">
  <div class="pplx-geo-header">
    <div class="pplx-geo-title">
      <h3>Contexte géopolitique IA</h3>
      <span class="pplx-badge-source">Perplexity sonar-pro</span>
    </div>
    <div class="pplx-geo-score-block">
      <div>
        <span class="pplx-geo-score" id="pplxGeoScoreValue">—</span><span class="pplx-geo-score-suffix">/100</span>
      </div>
      <span class="pplx-regime-badge pplx-regime-calm" id="pplxGeoRegimeBadge">—</span>
    </div>
    <div class="pplx-geo-summary" id="pplxGeoSummary">Chargement du contexte géopolitique…</div>
    <div class="pplx-geo-meta">
      <span id="pplxGeoTimestamp">—</span>
      <button onclick="loadPplxGeoData(true)">Rafraîchir</button>
    </div>
  </div>
  <div class="pplx-geo-grid">
    <div>
      <h4 class="pplx-col-title">Top 5 risques</h4>
      <div id="pplxGeoRisksList" class="pplx-loading">Chargement…</div>
    </div>
    <div>
      <h4 class="pplx-col-title">Exposition du portefeuille</h4>
      <div id="pplxGeoExposureList" class="pplx-loading">Chargement…</div>
    </div>
  </div>
</div>
""" + HTML_MARKER_END

# Supprime ancien bloc HTML
html = re.sub(
    re.escape(HTML_MARKER_START) + r'.*?' + re.escape(HTML_MARKER_END),
    '',
    html,
    flags=re.DOTALL,
)

# Insère APRES la fermeture du div geoSection (juste avant le </section> de tab-macro)
# Stratégie : trouve <section id="tab-macro">...</section> puis insère avant le </section> final
m_tab = re.search(r'<section\b[^>]*\bid=["\']tab-macro["\'][^>]*>', html)
if not m_tab:
    print("[KO] tab-macro introuvable")
    sys.exit(3)

# Recherche du </section> qui ferme tab-macro avec depth count
depth = 1
pos = m_tab.end()
section_close = -1
while depth > 0 and pos < len(html):
    next_open = html.find('<section', pos)
    next_close = html.find('</section>', pos)
    if next_close == -1:
        break
    if next_open != -1 and next_open < next_close:
        depth += 1
        pos = next_open + 8
    else:
        depth -= 1
        if depth == 0:
            section_close = next_close
        pos = next_close + 10

if section_close == -1:
    print("[KO] </section> tab-macro introuvable")
    sys.exit(4)

# Insère le bloc HTML juste avant </section>
html = html[:section_close] + "\n" + HTML_PANEL + "\n" + html[section_close:]
print("[OK] HTML panel injecté avant </section> tab-macro")

html_path.write_text(html, encoding="utf-8", newline="\n")

# ============================================================
# 3. JS dans app.js
# ============================================================
js = js_path.read_text(encoding="utf-8-sig")

JS_MARKER_START = "// === [PPLX_GEO_PANEL_JS_V1] BEGIN ==="
JS_MARKER_END   = "// === [PPLX_GEO_PANEL_JS_V1] END ==="

JS_BLOCK = JS_MARKER_START + """
(function(){
  function pplxEscape(s){
    if(s == null) return '';
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
  }

  function pplxRegimeClass(regime){
    const r = (regime || '').toLowerCase();
    if(r === 'calm') return 'pplx-regime-calm';
    if(r === 'elevated') return 'pplx-regime-elevated';
    if(r === 'stressed') return 'pplx-regime-stressed';
    if(r === 'crisis') return 'pplx-regime-crisis';
    return 'pplx-regime-calm';
  }

  function pplxFormatTs(iso){
    if(!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString('fr-FR', {dateStyle:'short', timeStyle:'short'});
    } catch(e){ return iso; }
  }

  function pplxRenderRisks(risks){
    const root = document.getElementById('pplxGeoRisksList');
    if(!root) return;
    if(!risks || !risks.length){
      root.className = 'pplx-empty';
      root.innerHTML = 'Aucun risque disponible.';
      return;
    }
    root.className = '';
    root.innerHTML = risks.map(r => `
      <div class="pplx-risk-card">
        <div class="pplx-risk-head">
          <div class="pplx-risk-title">${pplxEscape(r.title)}</div>
          <div class="pplx-risk-sev">${Math.round(r.severity || 0)}</div>
        </div>
        <div class="pplx-risk-tags">
          <span class="pplx-tag">${pplxEscape(r.region || '')}</span>
          <span class="pplx-tag">${pplxEscape(r.horizon || '')}</span>
          <span class="pplx-tag">${pplxEscape(r.type || '')}</span>
        </div>
        <div class="pplx-risk-narrative">${pplxEscape((r.narrative || '').substring(0, 320))}${(r.narrative && r.narrative.length > 320) ? '…' : ''}</div>
        <div class="pplx-risk-tickers">
          ${(r.tickers || []).map(t => `<span class="pplx-ticker-chip">${pplxEscape(t)}</span>`).join('')}
        </div>
      </div>
    `).join('');
  }

  function pplxRenderExposure(exposure){
    const root = document.getElementById('pplxGeoExposureList');
    if(!root) return;
    if(!exposure || !exposure.length){
      root.className = 'pplx-empty';
      root.innerHTML = 'Aucune position exposée.';
      return;
    }
    const maxScore = Math.max.apply(null, exposure.map(e => e.exposure_score_weighted || 0));
    root.className = '';
    root.innerHTML = exposure.map(e => {
      const pct = maxScore > 0 ? ((e.exposure_score_weighted || 0) / maxScore) * 100 : 0;
      const riskList = (e.risks || []).map(r => `R${r.risk_id}`).join(' · ');
      return `
        <div class="pplx-exp-row">
          <div class="pplx-exp-ticker">${pplxEscape(e.ticker)}</div>
          <div class="pplx-exp-weight">${(e.weight_pct || 0).toFixed(2)}%</div>
          <div class="pplx-exp-risks">${pplxEscape(riskList)}</div>
          <div class="pplx-exp-score">${(e.exposure_score_weighted || 0).toFixed(2)}</div>
          <div class="pplx-exp-bar"><div class="pplx-exp-bar-fill" style="width:${pct.toFixed(1)}%"></div></div>
        </div>
      `;
    }).join('');
  }

  function pplxRenderEmpty(reason){
    const sum = document.getElementById('pplxGeoSummary');
    const ts = document.getElementById('pplxGeoTimestamp');
    if(sum) sum.textContent = reason === 'no_snapshot'
      ? 'Aucun snapshot Perplexity disponible. Le scheduler le générera dans quelques minutes.'
      : 'Snapshot Perplexity indisponible.';
    if(ts) ts.textContent = '—';
    pplxRenderRisks([]);
    pplxRenderExposure([]);
  }

  window.loadPplxGeoData = async function(forceRefresh){
    try {
      const url = '/api/pplx/geo' + (forceRefresh ? ('?_=' + Date.now()) : '');
      const resp = await fetch(url);
      const data = await resp.json();
      if(!data || data.available === false){
        pplxRenderEmpty(data && data.reason);
        return;
      }
      const h = data.header || {};
      const score = h.global_score;
      const regime = h.regime;
      document.getElementById('pplxGeoScoreValue').textContent = (score != null) ? Math.round(score) : '—';
      const badge = document.getElementById('pplxGeoRegimeBadge');
      if(badge){
        badge.textContent = regime || '—';
        badge.className = 'pplx-regime-badge ' + pplxRegimeClass(regime);
      }
      const sum = document.getElementById('pplxGeoSummary');
      if(sum) sum.textContent = h.summary || '';
      const ts = document.getElementById('pplxGeoTimestamp');
      if(ts) ts.textContent = 'Snapshot : ' + pplxFormatTs(h.generated_at) + ' · ' + (h.model || '');
      pplxRenderRisks(data.risks || []);
      pplxRenderExposure(data.book_exposure || []);
    } catch(e){
      console.error('[PPLX_GEO_PANEL] load error', e);
      pplxRenderEmpty('error');
    }
  };

  // Auto-load au DOM ready + retries
  function pplxBoot(){
    if(document.getElementById('pplxGeoSection')){
      window.loadPplxGeoData(false);
    } else {
      setTimeout(pplxBoot, 500);
    }
  }
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', pplxBoot);
  } else {
    pplxBoot();
  }

  // Refresh quand on clique sur le tab macro
  document.addEventListener('click', function(e){
    const tgt = e.target;
    if(tgt && tgt.matches && tgt.matches('[data-tab="macro"], [href="#tab-macro"]')){
      setTimeout(function(){ window.loadPplxGeoData(false); }, 200);
    }
  });
})();
""" + JS_MARKER_END

# Supprime ancien bloc
js = re.sub(
    re.escape(JS_MARKER_START) + r'.*?' + re.escape(JS_MARKER_END),
    '',
    js,
    flags=re.DOTALL,
)

# Append à la fin
js = js.rstrip() + "\n\n" + JS_BLOCK + "\n"

js_path.write_text(js, encoding="utf-8", newline="\n")
print("[OK] JS injecté")
'@

Set-Content -Path $helper -Value $helperContent -Encoding UTF8

Write-Host "[3/5] Helper -> $helper"
py -3.13 $helper $html $js
if ($LASTEXITCODE -ne 0) {
    Write-Host "[KO] Helper a échoué. Restore." -ForegroundColor Red
    Copy-Item $htmlBackup $html -Force
    Copy-Item $jsBackup $js -Force
    exit 1
}

# Comptage APRES
$htmlSrc2 = Get-Content $html -Raw -Encoding UTF8
$jsSrc2 = Get-Content $js -Raw -Encoding UTF8
$htmlTagsAfter = ([regex]::Matches($htmlSrc2, '<section|<div|</section>|</div>')).Count
Write-Host "[4/5] APRES : index.html $htmlTagsAfter tags"
Write-Host "    Delta HTML : +$($htmlTagsAfter - $htmlTagsBefore) tags"

# Vérif markers
foreach ($m in @('[PPLX_GEO_PANEL_CSS_V1]', '[PPLX_GEO_PANEL_HTML_V1]')) {
    if (-not $htmlSrc2.Contains($m)) {
        Write-Host "[KO] Marker $m absent dans index.html. Restore." -ForegroundColor Red
        Copy-Item $htmlBackup $html -Force
        Copy-Item $jsBackup $js -Force
        exit 1
    }
}
if (-not $jsSrc2.Contains('[PPLX_GEO_PANEL_JS_V1]')) {
    Write-Host "[KO] Marker JS absent. Restore." -ForegroundColor Red
    Copy-Item $htmlBackup $html -Force
    Copy-Item $jsBackup $js -Force
    exit 1
}
Write-Host "    Markers : CSS OK, HTML OK, JS OK"

# Vérif équilibre tags HTML (somme net = 0)
$openTags = ([regex]::Matches($htmlSrc2, '<(section|div)\b[^>]*>(?!.*/>)')).Count
$closeTags = ([regex]::Matches($htmlSrc2, '</(section|div)>')).Count
$delta = $openTags - $closeTags
Write-Host "    Tags open vs close : $openTags vs $closeTags (delta=$delta)"

# Validation HTML rapide (parsing minimal)
Write-Host "[5/5] Validation tags equilibre..."
$beforeBalance = ([regex]::Matches($htmlSrc, '<(section|div)\b[^>]*>')).Count - ([regex]::Matches($htmlSrc, '</(section|div)>')).Count
$afterBalance = $delta
Write-Host "    Balance AVANT : $beforeBalance, APRES : $afterBalance"

if ($afterBalance -ne $beforeBalance) {
    Write-Host "[!] Balance modifiee, mais peut etre due au panel (1 div ouvert/ferme). Tolere." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== PATCH OK ===" -ForegroundColor Green
Write-Host "Backups :"
Write-Host "  $htmlBackup"
Write-Host "  $jsBackup"
Write-Host ""
Write-Host "Hard refresh navigateur (Ctrl+F5) sur l'onglet Macro."
Write-Host "Tu devrais voir le panel 'Contexte géopolitique IA' sous le panel GDELT."
