# [PPLX_GEO_PANEL_RESTORE_JS_V1]
# Restaure le bloc JavaScript du panel geo qui a ete supprime par un patch precedent.
# IDs DOM cibles (verifies dans index.html) :
#   - pplxGeoScoreValue
#   - pplxGeoRegimeBadge
#   - pplxGeoSummary
#   - pplxGeoTimestamp
#   - pplxGeoRisksList     (et non pplxGeoRisksGrid)
#   - pplxGeoExposureList
#
# Le script :
#   1) Backup index.html.bak.<ts>
#   2) Verifie qu'aucun bloc V1_JS n'existe deja (idempotence)
#   3) Injecte le bloc JS juste avant </body>
#   4) Valide en relisant les markers
#
# Usage : py -3.13 nextones-fix-geo-restore-js.py

from pathlib import Path
import shutil
import time
import re

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
MARK_BEGIN = "<!-- [PPLX_GEO_PANEL_V1_JS_BEGIN] -->"
MARK_END = "<!-- [PPLX_GEO_PANEL_V1_JS_END] -->"

JS_BLOCK = MARK_BEGIN + r"""
<script>
(function(){
  // === Helpers ===
  function pplxFormatTs(ts){
    if(!ts) return '—';
    try {
      var d = new Date(ts);
      if(isNaN(d.getTime())) return String(ts);
      var pad = function(n){ return (n<10?'0':'')+n; };
      return d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate())+' '
           + pad(d.getHours())+':'+pad(d.getMinutes());
    } catch(e){ return String(ts); }
  }
  function pplxRegimeClass(regime){
    var r = String(regime||'').toLowerCase();
    if(r==='crisis')   return 'pplx-regime-crisis';
    if(r==='stressed') return 'pplx-regime-stressed';
    if(r==='elevated') return 'pplx-regime-elevated';
    return 'pplx-regime-calm';
  }
  function pplxEsc(s){
    return String(s==null?'':s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // === Rendering ===
  function pplxRenderRisks(risks){
    var box = document.getElementById('pplxGeoRisksList');
    if(!box) return;
    if(!risks || !risks.length){
      box.className = 'pplx-empty';
      box.innerHTML = 'Aucun risque identifie.';
      return;
    }
    box.className = '';
    box.innerHTML = risks.map(function(r){
      var tickers = (r.tickers||[]).map(function(t){
        return '<span class="pplx-ticker-chip">'+pplxEsc(t)+'</span>';
      }).join('');
      var sectors = (r.sectors||[]).map(function(s){
        return '<span class="pplx-tag">'+pplxEsc(s)+'</span>';
      }).join('');
      var sev = Math.round(Number(r.severity)||0);
      return ''
        + '<div class="pplx-risk-card">'
        +   '<div class="pplx-risk-head">'
        +     '<div class="pplx-risk-title">'+pplxEsc(r.title||'')+'</div>'
        +     '<div class="pplx-risk-sev">'+sev+'</div>'
        +   '</div>'
        +   '<div class="pplx-risk-tags">'
        +     '<span class="pplx-tag">'+pplxEsc(r.region||'?')+'</span>'
        +     '<span class="pplx-tag">'+pplxEsc(r.horizon||'?')+'</span>'
        +     '<span class="pplx-tag">'+pplxEsc(r.type||'?')+'</span>'
        +     sectors
        +   '</div>'
        +   (r.narrative ? '<div class="pplx-risk-narrative">'+pplxEsc(r.narrative)+'</div>' : '')
        +   (tickers ? '<div class="pplx-risk-tickers">'+tickers+'</div>' : '')
        + '</div>';
    }).join('');
  }

  function pplxRenderExposure(items){
    var box = document.getElementById('pplxGeoExposureList');
    if(!box) return;
    if(!items || !items.length){
      box.className = 'pplx-empty';
      box.innerHTML = 'Aucune exposition identifiee dans le portefeuille.';
      return;
    }
    box.className = '';
    var max = 1;
    items.forEach(function(it){
      var v = Number(it.exposure_score_weighted)||0;
      if(v>max) max = v;
    });
    box.innerHTML = items.map(function(it){
      var w = Number(it.weight_pct)||0;
      var s = Number(it.exposure_score_weighted)||0;
      var pct = Math.max(2, Math.round((s/max)*100));
      var nrisks = (it.risks||[]).length;
      return ''
        + '<div class="pplx-exp-row">'
        +   '<div class="pplx-exp-ticker">'+pplxEsc(it.ticker||'')+'</div>'
        +   '<div class="pplx-exp-weight">'+w.toFixed(2)+'%</div>'
        +   '<div class="pplx-exp-risks">'+nrisks+' risque'+(nrisks>1?'s':'')+'</div>'
        +   '<div class="pplx-exp-bar"><div class="pplx-exp-bar-fill" style="width:'+pct+'%"></div></div>'
        +   '<div class="pplx-exp-score">'+s.toFixed(2)+'</div>'
        + '</div>';
    }).join('');
  }

  function pplxRenderEmpty(reason){
    var sum = document.getElementById('pplxGeoSummary');
    var ts = document.getElementById('pplxGeoTimestamp');
    if(sum) sum.textContent = (reason === 'no_snapshot')
      ? 'Aucun snapshot Perplexity disponible. Le scheduler le generera dans quelques minutes.'
      : 'Snapshot Perplexity indisponible (' + (reason||'erreur') + ').';
    if(ts) ts.textContent = '—';
    pplxRenderRisks([]);
    pplxRenderExposure([]);
  }

  // === Main loader ===
  window.loadPplxGeoData = async function(forceRefresh){
    try {
      var url = '/api/pplx/geo' + (forceRefresh ? ('?_=' + Date.now()) : '');
      var resp = await fetch(url);
      if(!resp.ok){
        pplxRenderEmpty('http_'+resp.status);
        return;
      }
      var data = await resp.json();
      if(!data || data.available === false){
        pplxRenderEmpty(data && data.reason);
        return;
      }
      var h = data.header || {};
      var score = h.global_score;
      var regime = h.regime;
      var sv = document.getElementById('pplxGeoScoreValue');
      if(sv) sv.textContent = (score != null) ? Math.round(score) : '—';
      var badge = document.getElementById('pplxGeoRegimeBadge');
      if(badge){
        badge.textContent = regime || '—';
        badge.className = 'pplx-regime-badge ' + pplxRegimeClass(regime);
      }
      var sum = document.getElementById('pplxGeoSummary');
      if(sum) sum.textContent = h.summary || '';
      var ts = document.getElementById('pplxGeoTimestamp');
      if(ts) ts.textContent = 'Snapshot : ' + pplxFormatTs(h.generated_at) + ' - ' + (h.model || '');
      pplxRenderRisks(data.risks || []);
      pplxRenderExposure(data.book_exposure || []);
    } catch(e){
      console.error('[PPLX_GEO_PANEL] load error', e);
      pplxRenderEmpty('exception');
    }
  };

  // === Boot ===
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
    var tgt = e.target;
    if(tgt && tgt.matches && tgt.matches('[data-tab="macro"], [href="#tab-macro"]')){
      setTimeout(function(){ window.loadPplxGeoData(false); }, 200);
    }
  });
})();
</script>
""" + MARK_END + "\n"


def main():
    if not HTML.exists():
        print(f"[ERR] HTML introuvable : {HTML}")
        return

    raw = HTML.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] Fichier : {HTML}")
    print(f"[INFO] Taille avant : {len(raw)} chars")

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = HTML.with_suffix(f".html.bak.{ts}")
    shutil.copy2(HTML, backup)
    print(f"[OK]   Backup : {backup}")

    # Supprime ancien bloc V1_JS s'il existe (idempotent)
    if MARK_BEGIN in raw and MARK_END in raw:
        pattern = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"\n?", re.DOTALL)
        raw = pattern.sub("", raw)
        print("[OK]   Ancien bloc V1_JS supprime")
    else:
        print("[OK]   Pas d'ancien bloc V1_JS (premiere injection)")

    # Injecte avant </body>
    if "</body>" not in raw:
        print("[ERR]  </body> introuvable, abort")
        return
    raw_new = raw.replace("</body>", JS_BLOCK + "</body>", 1)
    print(f"[INFO] Taille apres : {len(raw_new)} chars (+{len(raw_new)-len(raw)})")

    HTML.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK]   Ecriture index.html (utf-8 sans BOM)")

    # Validation
    check = HTML.read_text(encoding="utf-8-sig", errors="replace")
    tags_required = [
        "PPLX_GEO_PANEL_V1_JS_BEGIN",
        "PPLX_GEO_PANEL_V1_JS_END",
        "window.loadPplxGeoData",
        "function pplxRenderRisks",
        "function pplxRenderExposure",
        "function pplxBoot",
    ]
    all_ok = True
    print("\n[VALIDATION]")
    for t in tags_required:
        n = check.count(t)
        flag = "OK" if n >= 1 else "MISS"
        if n < 1:
            all_ok = False
        print(f"  [{flag}] {t:35} count={n}")

    if all_ok:
        print("\n[SUCCESS] Patch applique. Recharge ton navigateur (Ctrl+Shift+R hard refresh).")
        print("          Le panel geo devrait s'afficher avec score=68, regime=stressed, 5 risques.")
    else:
        print("\n[FAIL] Validation incomplete, regarde les MISS ci-dessus.")


if __name__ == "__main__":
    main()
