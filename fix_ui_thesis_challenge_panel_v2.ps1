# fix_ui_thesis_challenge_panel_v2.ps1
# Ajoute une 3e section "Thesis Challenges" au panel Perplexity Insights
# V2 :
#  - Le clic recupere le detail complet via /api/pplx/thesis-challenge/{id}
#    (le cycle-snapshot allege ne contient pas counter_arguments/blind_spots/citations)
#  - Gere bien les counter_arguments comme objets {argument, severity, evidence_type}
#  - confidence_in_challenge est une string (low/medium/high), pas un number
# Markers idempotents : [PPLX_THESIS_PANEL_V2_HTML], [PPLX_THESIS_PANEL_V2_JS]

$ErrorActionPreference = 'Stop'
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$indexPath = Join-Path $root "index.html"
$appJsPath = Join-Path $root "app.js"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

if (-not (Test-Path $indexPath)) { throw "index.html introuvable: $indexPath" }
if (-not (Test-Path $appJsPath)) { throw "app.js introuvable: $appJsPath" }

# Backups
Copy-Item $indexPath "$indexPath.bak_thesis_panel_v2_$stamp" -Force
Copy-Item $appJsPath "$appJsPath.bak_thesis_panel_v2_$stamp" -Force
Write-Host "[BACKUP] index.html + app.js sauvegardes ($stamp)" -ForegroundColor Cyan

# ============================================================
# 1. PATCH index.html : ajouter section HTML dans le panel Perplexity
# ============================================================
$helperHtml = Join-Path $env:TEMP "patch_index_thesis_panel_v2.py"
$helperHtmlContent = @'
# -*- coding: utf-8 -*-
import sys, re
from pathlib import Path

path = Path(sys.argv[1])
src = path.read_text(encoding="utf-8-sig")

MARKER = "[PPLX_THESIS_PANEL_V2_HTML]"
# Skip si V1 ou V2 deja appliquees
if MARKER in src or "[PPLX_THESIS_PANEL_V1_HTML]" in src:
    print("[SKIP] Marker thesis panel HTML deja present (V1 ou V2)")
    sys.exit(0)

# Insertion : juste apres la section equity table id="pplx-equity-table"
pattern = re.compile(
    r'(<table[^>]*id="pplx-equity-table"[^>]*>.*?</table>\s*</div>)',
    re.DOTALL
)

block = """
<!-- """ + MARKER + """ -->
<div class="pplx-section" id="pplx-thesis-section" style="margin-top:16px;">
  <h3 style="color:#e0e0e0;margin:8px 0;font-size:14px;">Thesis Challenges (Perplexity)</h3>
  <div style="font-size:11px;color:#888;margin-bottom:6px;">
    Auto-challenge sur top-5 theses haute conviction. Badge rouge = remise en cause forte.
  </div>
  <table id="pplx-thesis-table" style="width:100%;border-collapse:collapse;font-size:12px;color:#ddd;">
    <thead>
      <tr style="background:#222;color:#aaa;">
        <th style="padding:4px;text-align:left;">Ticker</th>
        <th style="padding:4px;text-align:left;">Side</th>
        <th style="padding:4px;text-align:right;">Conv</th>
        <th style="padding:4px;text-align:right;">Challenge</th>
        <th style="padding:4px;text-align:left;">Verdict</th>
        <th style="padding:4px;text-align:left;">TS</th>
      </tr>
    </thead>
    <tbody id="pplx-thesis-tbody">
      <tr><td colspan="6" style="padding:8px;color:#666;text-align:center;">Chargement...</td></tr>
    </tbody>
  </table>
</div>
<!-- /""" + MARKER + """ -->
"""

m = pattern.search(src)
if not m:
    print("[ERROR] Section equity non trouvee dans index.html")
    sys.exit(2)

new_src = src[:m.end()] + block + src[m.end():]
path.write_text(new_src, encoding="utf-8")
print("[OK] Section HTML thesis injectee apres equity table")
'@
Set-Content -Path $helperHtml -Value $helperHtmlContent -Encoding UTF8
py -3.13 $helperHtml $indexPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ROLLBACK] index.html restauration..." -ForegroundColor Red
    Copy-Item "$indexPath.bak_thesis_panel_v2_$stamp" $indexPath -Force
    throw "Patch HTML echoue (exit=$LASTEXITCODE)"
}

# ============================================================
# 2. PATCH app.js : ajouter logique JS thesis_challenges
# ============================================================
$helperJs = Join-Path $env:TEMP "patch_appjs_thesis_panel_v2.py"
$helperJsContent = @'
# -*- coding: utf-8 -*-
import sys, re
from pathlib import Path

path = Path(sys.argv[1])
src = path.read_text(encoding="utf-8-sig")

MARKER = "[PPLX_THESIS_PANEL_V2_JS]"
if MARKER in src or "[PPLX_THESIS_PANEL_V1_JS]" in src:
    print("[SKIP] Marker thesis panel JS deja present (V1 ou V2)")
    sys.exit(0)

# Bloc JS a ajouter en fin de fichier app.js
js_block = r"""

// """ + MARKER + r"""
(function(){
  function escHtml(s){
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function badgeForChallenge(score){
    if (score == null) return '<span style="color:#666;">-</span>';
    let color = '#4caf50';
    let label = Number(score).toFixed(0);
    if (score > 70) color = '#e53935';
    else if (score > 40) color = '#ffb300';
    return '<span style="background:' + color + ';color:#fff;padding:2px 6px;border-radius:3px;font-weight:bold;">' + label + '</span>';
  }

  function badgeVerdict(v){
    if (!v) return '<span style="color:#666;">-</span>';
    const map = {
      'thesis_holds':           ['#4caf50','HOLDS'],
      'moderate_concerns':      ['#ffb300','CONCERNS'],
      'significant_challenge':  ['#fb8c00','CHALLENGE'],
      'thesis_undermined':      ['#e53935','UNDERMINED']
    };
    const def = map[v] || ['#888', v];
    return '<span style="background:' + def[0] + ';color:#fff;padding:1px 5px;border-radius:3px;font-size:10px;">' + escHtml(def[1]) + '</span>';
  }

  function badgeSeverity(sev){
    const map = { 'low':'#4caf50', 'medium':'#ffb300', 'high':'#e53935' };
    const color = map[sev] || '#888';
    return '<span style="background:' + color + ';color:#fff;padding:1px 4px;border-radius:2px;font-size:9px;margin-right:4px;text-transform:uppercase;">' + escHtml(sev||'?') + '</span>';
  }

  function renderThesisChallenges(rows){
    const tbody = document.getElementById('pplx-thesis-tbody');
    if (!tbody) return;
    if (!rows || rows.length === 0){
      tbody.innerHTML = '<tr><td colspan="6" style="padding:8px;color:#666;text-align:center;">Aucun challenge disponible</td></tr>';
      return;
    }
    rows.sort(function(a,b){ return (b.challenge_score||0) - (a.challenge_score||0); });
    let html = '';
    rows.forEach(function(r){
      const ts = (r.ts && typeof r.ts === 'number') ? new Date(r.ts*1000).toISOString().slice(0,16).replace('T',' ') : (String(r.ts||'').slice(0,16));
      html += '<tr class="pplx-thesis-row" data-thesis-id="' + escHtml(r.thesis_id||'') + '" style="cursor:pointer;border-bottom:1px solid #2a2a2a;">'
            + '<td style="padding:4px;">' + escHtml(r.ticker||'?') + '</td>'
            + '<td style="padding:4px;color:' + (r.side==='SHORT'?'#e57373':(r.side==='LONG'?'#81c784':'#888')) + ';">' + escHtml(r.side||'-') + '</td>'
            + '<td style="padding:4px;text-align:right;">' + (r.conviction!=null?Number(r.conviction).toFixed(1):'-') + '</td>'
            + '<td style="padding:4px;text-align:right;">' + badgeForChallenge(r.challenge_score) + '</td>'
            + '<td style="padding:4px;">' + badgeVerdict(r.verdict) + '</td>'
            + '<td style="padding:4px;color:#777;font-size:10px;">' + escHtml(ts) + '</td>'
            + '</tr>';
    });
    tbody.innerHTML = html;
    Array.prototype.forEach.call(tbody.querySelectorAll('.pplx-thesis-row'), function(tr){
      tr.addEventListener('click', async function(){
        const tid = tr.getAttribute('data-thesis-id');
        await showThesisChallengeDetail(tid);
      });
    });
  }

  async function showThesisChallengeDetail(thesisId){
    // Recupere le detail complet via /api/pplx/thesis-challenge/{id}
    const existing = document.getElementById('pplx-thesis-modal');
    if (existing) existing.remove();

    const modal = document.createElement('div');
    modal.id = 'pplx-thesis-modal';
    modal.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#0f0f0f;border:1px solid #444;border-radius:5px;z-index:99999;box-shadow:0 4px 20px rgba(0,0,0,0.8);max-height:85vh;width:760px;max-width:90vw;overflow:auto;padding:14px;color:#ddd;';
    modal.innerHTML = '<div style="color:#888;padding:20px;text-align:center;">Chargement du challenge...</div>';
    document.body.appendChild(modal);

    let r;
    try {
      const resp = await fetch('/api/pplx/thesis-challenge/' + encodeURIComponent(thesisId), { credentials: 'include' });
      if (!resp.ok) {
        modal.innerHTML = '<div style="color:#e57373;padding:20px;">Erreur HTTP ' + resp.status + '</div>' + closeBtn();
        return;
      }
      r = await resp.json();
    } catch (e) {
      modal.innerHTML = '<div style="color:#e57373;padding:20px;">Erreur reseau: ' + escHtml(String(e)) + '</div>' + closeBtn();
      return;
    }

    const counter = Array.isArray(r.counter_arguments) ? r.counter_arguments : [];
    const blind = Array.isArray(r.blind_spots) ? r.blind_spots : [];
    const facts = Array.isArray(r.supporting_facts_against) ? r.supporting_facts_against : [];
    const cites = Array.isArray(r.citations) ? r.citations : [];

    let html = '<h3 style="margin:0 0 6px 0;">' + escHtml(r.ticker||'?') + ' / ' + escHtml(r.side||'-') + '  '
      + badgeForChallenge(r.challenge_score) + '  ' + badgeVerdict(r.verdict) + '</h3>'
      + '<div style="font-size:11px;color:#888;margin-bottom:8px;">Conviction initiale: ' + (r.conviction!=null?Number(r.conviction).toFixed(1):'-')
      + ' &middot; Confiance challenge: ' + escHtml(r.confidence_in_challenge||'-')
      + ' &middot; ' + escHtml(r.model||'') + '</div>';

    if (r.source_thesis_summary){
      html += '<div style="background:#1a1a1a;padding:6px;border-radius:3px;margin-bottom:8px;font-size:11px;"><b>These initiale:</b><br>' + escHtml(r.source_thesis_summary) + '</div>';
    }
    if (r.alternative_thesis){
      html += '<div style="background:#2a1a1a;padding:6px;border-radius:3px;margin-bottom:8px;font-size:11px;border-left:3px solid #e53935;"><b>These alternative:</b><br>' + escHtml(r.alternative_thesis) + '</div>';
    }
    if (counter.length){
      html += '<div style="margin-bottom:6px;"><b style="color:#ffb300;">Counter-arguments:</b><ul style="margin:4px 0;padding-left:18px;font-size:11px;list-style:none;">';
      counter.forEach(function(c){
        if (typeof c === 'string') {
          html += '<li style="margin-bottom:4px;">' + escHtml(c) + '</li>';
        } else if (c && c.argument) {
          html += '<li style="margin-bottom:4px;">' + badgeSeverity(c.severity) + '<span style="color:#888;font-size:10px;">[' + escHtml(c.evidence_type||'?') + ']</span> ' + escHtml(c.argument) + '</li>';
        }
      });
      html += '</ul></div>';
    }
    if (facts.length){
      html += '<div style="margin-bottom:6px;"><b style="color:#e57373;">Faits contre la these:</b><ul style="margin:4px 0;padding-left:18px;font-size:11px;">';
      facts.forEach(function(f){ html += '<li>' + escHtml(f) + '</li>'; });
      html += '</ul></div>';
    }
    if (blind.length){
      html += '<div style="margin-bottom:6px;"><b style="color:#ba68c8;">Angles morts:</b><ul style="margin:4px 0;padding-left:18px;font-size:11px;">';
      blind.forEach(function(b){ html += '<li>' + escHtml(b) + '</li>'; });
      html += '</ul></div>';
    }
    if (cites.length){
      html += '<div style="margin-top:8px;font-size:10px;color:#888;"><b>Sources:</b><br>';
      cites.forEach(function(u){
        const url = String(u||'');
        html += '<a href="' + escHtml(url) + '" target="_blank" rel="noopener" style="color:#64b5f6;">' + escHtml(url) + '</a><br>';
      });
      html += '</div>';
    }
    html += closeBtn();
    modal.innerHTML = html;
  }

  function closeBtn(){
    return '<div style="margin-top:10px;text-align:right;"><button onclick="document.getElementById(\'pplx-thesis-modal\').remove();" style="background:#444;color:#fff;border:0;padding:5px 12px;border-radius:3px;cursor:pointer;">Fermer</button></div>';
  }

  async function refreshThesisChallenges(){
    try {
      const resp = await fetch('/api/pplx/thesis-challenges?limit=20', { credentials: 'include' });
      if (!resp.ok) {
        const tbody = document.getElementById('pplx-thesis-tbody');
        if (tbody) tbody.innerHTML = '<tr><td colspan="6" style="padding:8px;color:#888;text-align:center;">HTTP ' + resp.status + '</td></tr>';
        return;
      }
      const data = await resp.json();
      const rows = (data && data.items) || [];
      renderThesisChallenges(rows);
    } catch (e) {
      console.warn('[pplx-thesis] refresh error', e);
    }
  }

  window.refreshThesisChallenges = refreshThesisChallenges;
  if (document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){
      refreshThesisChallenges();
      setInterval(refreshThesisChallenges, 5*60*1000);
    });
  } else {
    refreshThesisChallenges();
    setInterval(refreshThesisChallenges, 5*60*1000);
  }
})();
// /""" + MARKER + r"""
"""

new_src = src.rstrip() + "\n" + js_block + "\n"
path.write_text(new_src, encoding="utf-8")
print("[OK] Bloc JS thesis challenges V2 ajoute en fin de app.js")
'@
Set-Content -Path $helperJs -Value $helperJsContent -Encoding UTF8
py -3.13 $helperJs $appJsPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ROLLBACK] app.js restauration..." -ForegroundColor Red
    Copy-Item "$appJsPath.bak_thesis_panel_v2_$stamp" $appJsPath -Force
    throw "Patch JS echoue (exit=$LASTEXITCODE)"
}

Write-Host "" -ForegroundColor Green
Write-Host "[OK] Patch UI thesis challenges V2 applique" -ForegroundColor Green
Write-Host "  - HTML  : section #pplx-thesis-section ajoutee dans index.html" -ForegroundColor Gray
Write-Host "  - JS    : fetch /api/pplx/thesis-challenges (liste) + /api/pplx/thesis-challenge/{id} (detail)" -ForegroundColor Gray
Write-Host "  - Badge : rouge si challenge>70, orange si >40, vert sinon" -ForegroundColor Gray
Write-Host "  - Clic  : modal avec counter_arguments severity-coded, blind_spots, citations" -ForegroundColor Gray
Write-Host "  - HTML  : escape contre XSS" -ForegroundColor Gray
Write-Host "" -ForegroundColor Green
Write-Host "Redemarrer uvicorn pour servir l'UI patchee" -ForegroundColor Yellow
