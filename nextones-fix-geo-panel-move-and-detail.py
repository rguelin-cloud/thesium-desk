# -*- coding: utf-8 -*-
"""
Patch UI :
  1. Deplace la section "Contexte geopolitique IA" en haut de la page MACRO
     (via JS sur DOMContentLoaded - pas de modif HTML statique)
  2. Ajoute un bouton "Voir l'article" sur chaque carte risque
  3. Ajoute un modal global pour afficher le detail complet (narrative + mechanism
     + catalysts + sources + tickers)

Idempotent :
  - JS  : marker [PPLX_GEO_DETAIL_V1]
  - CSS : marker [PPLX_GEO_DETAIL_CSS_V1]
  - HTML: marker [PPLX_GEO_DETAIL_MODAL_V1]
"""
import sys
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
INDEX = ROOT / "index.html"
APP_JS = ROOT / "app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARKER_CSS = "[PPLX_GEO_DETAIL_CSS_V1]"
MARKER_HTML = "[PPLX_GEO_DETAIL_MODAL_V1]"
MARKER_JS = "[PPLX_GEO_DETAIL_V1]"


CSS_BLOCK = f"""
/* === {MARKER_CSS} : Modal detail risque geopolitique === */
.pplx-geo-detail-backdrop {{
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.55);
  z-index: 9998;
  display: none;
  align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}}
.pplx-geo-detail-backdrop.open {{ display: flex; }}
.pplx-geo-detail-modal {{
  background: var(--color-surface, #1a1d24);
  color: var(--color-text, #e7eaf0);
  border: 1px solid var(--color-border, #2a2f3a);
  border-radius: 12px;
  width: min(820px, 94vw);
  max-height: 90vh;
  overflow-y: auto;
  padding: 24px 28px 28px;
  box-shadow: 0 24px 60px rgba(0,0,0,0.6);
  position: relative;
}}
.pplx-geo-detail-modal h3 {{
  margin: 0 0 12px;
  font-size: 18px;
  padding-right: 36px;
  line-height: 1.35;
}}
.pplx-geo-detail-close {{
  position: absolute; top: 14px; right: 16px;
  background: transparent; border: none;
  color: var(--color-text); font-size: 22px;
  cursor: pointer; line-height: 1; opacity: 0.7;
}}
.pplx-geo-detail-close:hover {{ opacity: 1; }}
.pplx-geo-detail-meta {{
  display: flex; flex-wrap: wrap; gap: 6px;
  margin-bottom: 14px; padding-bottom: 14px;
  border-bottom: 1px solid var(--color-border);
}}
.pplx-geo-detail-tag {{
  font-size: 11px;
  padding: 3px 9px; border-radius: 10px;
  background: rgba(255,255,255,0.05);
  color: var(--color-text-muted, #9aa3b2);
}}
.pplx-geo-detail-severity {{
  font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 10px;
  background: var(--color-primary, #2bb8a8);
  color: white;
}}
.pplx-geo-detail-section {{ margin-top: 16px; }}
.pplx-geo-detail-section h4 {{
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
  margin: 0 0 8px;
}}
.pplx-geo-detail-section p {{
  margin: 0; font-size: 14px;
  line-height: 1.55;
}}
.pplx-geo-detail-section ul {{
  margin: 0; padding-left: 20px;
}}
.pplx-geo-detail-section li {{
  font-size: 13px; line-height: 1.5;
  margin-bottom: 6px;
}}
.pplx-geo-detail-tickers {{
  display: flex; flex-wrap: wrap; gap: 6px;
}}
.pplx-geo-detail-ticker {{
  font-size: 11px; font-weight: 600;
  padding: 3px 9px;
  background: rgba(43,184,168,0.15);
  border: 1px solid rgba(43,184,168,0.3);
  color: var(--color-primary, #2bb8a8);
  border-radius: 6px;
}}
.pplx-geo-detail-sources a {{
  display: block;
  font-size: 12px;
  color: var(--color-primary);
  text-decoration: none;
  margin-bottom: 4px;
  word-break: break-all;
}}
.pplx-geo-detail-sources a:hover {{ text-decoration: underline; }}

/* Bouton "Voir l article" sur chaque carte de risque */
.pplx-geo-detail-btn {{
  margin-top: 8px;
  background: transparent;
  border: 1px solid var(--color-border, #2a2f3a);
  color: var(--color-text-muted, #9aa3b2);
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px;
  transition: all 0.15s;
}}
.pplx-geo-detail-btn:hover {{
  background: var(--color-primary, #2bb8a8);
  color: white;
  border-color: var(--color-primary, #2bb8a8);
}}
/* === END {MARKER_CSS} === */
"""


HTML_MODAL = f"""
<!-- {MARKER_HTML} : Modal detail risque geo -->
<div id="pplxGeoDetailBackdrop" class="pplx-geo-detail-backdrop" onclick="if(event.target===this)pplxGeoDetailClose()">
  <div class="pplx-geo-detail-modal" role="dialog" aria-modal="true">
    <button class="pplx-geo-detail-close" onclick="pplxGeoDetailClose()" aria-label="Fermer">×</button>
    <div id="pplxGeoDetailBody"></div>
  </div>
</div>
<!-- END {MARKER_HTML} -->
"""


JS_BLOCK = f"""
/* === {MARKER_JS} : Move geo section + bouton detail risque === */
(function() {{
  if (window.pplxGeoDetailOpen) {{ return; }}

  // Storage des risques courants (mis a jour quand on render)
  window._pplxGeoRisks = window._pplxGeoRisks || [];

  function _escapeHtml(s) {{
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
  }}

  // Convertit les citations [N] en liens cliquables si la source N existe
  function _linkifyCitations(text, sources) {{
    if (!text) return '';
    let escaped = _escapeHtml(text);
    if (!Array.isArray(sources) || sources.length === 0) return escaped;
    return escaped.replace(/\\[(\\d+)\\]/g, (m, n) => {{
      const idx = parseInt(n, 10) - 1;
      if (idx >= 0 && idx < sources.length) {{
        return `<a href="${{_escapeHtml(sources[idx])}}" target="_blank" rel="noopener" style="color:var(--color-primary);text-decoration:none;">[${{n}}]</a>`;
      }}
      return m;
    }});
  }}

  window.pplxGeoDetailOpen = function(riskId) {{
    const risks = window._pplxGeoRisks || [];
    const risk = risks.find(r => (r.risk_id === riskId) || (r.id === riskId));
    if (!risk) {{
      console.warn('[PPLX-GEO-DETAIL] Risque introuvable:', riskId);
      return;
    }}
    const bd = document.getElementById('pplxGeoDetailBackdrop');
    const body = document.getElementById('pplxGeoDetailBody');
    if (!bd || !body) return;

    const sources = Array.isArray(risk.sources) ? risk.sources : [];
    const tickers = Array.isArray(risk.tickers) ? risk.tickers : [];
    const sectors = Array.isArray(risk.sectors) ? risk.sectors : [];
    const catalysts = Array.isArray(risk.catalysts) ? risk.catalysts : [];
    const sev = (typeof risk.severity === 'number') ? Math.round(risk.severity) : '';
    const narrative = risk.narrative || risk.description || '';
    const mechanism = risk.mechanism || '';

    body.innerHTML = `
      <h3>${{_escapeHtml(risk.title || risk.risk_id || '')}}</h3>
      <div class="pplx-geo-detail-meta">
        ${{sev !== '' ? `<span class="pplx-geo-detail-severity">Severite ${{sev}}/100</span>` : ''}}
        ${{risk.region ? `<span class="pplx-geo-detail-tag">${{_escapeHtml(risk.region)}}</span>` : ''}}
        ${{risk.horizon ? `<span class="pplx-geo-detail-tag">${{_escapeHtml(risk.horizon)}}</span>` : ''}}
        ${{risk.type ? `<span class="pplx-geo-detail-tag">${{_escapeHtml(risk.type)}}</span>` : ''}}
      </div>
      ${{narrative ? `
      <div class="pplx-geo-detail-section">
        <h4>Contexte</h4>
        <p>${{_linkifyCitations(narrative, sources)}}</p>
      </div>` : ''}}
      ${{catalysts.length ? `
      <div class="pplx-geo-detail-section">
        <h4>Catalystes potentiels</h4>
        <ul>${{catalysts.map(c => `<li>${{_linkifyCitations(c, sources)}}</li>`).join('')}}</ul>
      </div>` : ''}}
      ${{mechanism ? `
      <div class="pplx-geo-detail-section">
        <h4>Mecanisme de transmission au portefeuille</h4>
        <p>${{_linkifyCitations(mechanism, sources)}}</p>
      </div>` : ''}}
      ${{tickers.length ? `
      <div class="pplx-geo-detail-section">
        <h4>Symboles impactes</h4>
        <div class="pplx-geo-detail-tickers">${{tickers.map(t => `<span class="pplx-geo-detail-ticker">${{_escapeHtml(t)}}</span>`).join('')}}</div>
      </div>` : ''}}
      ${{sectors.length ? `
      <div class="pplx-geo-detail-section">
        <h4>Secteurs</h4>
        <p style="font-size:13px;color:var(--color-text-muted);">${{sectors.map(s => _escapeHtml(s)).join(' \\u00b7 ')}}</p>
      </div>` : ''}}
      ${{sources.length ? `
      <div class="pplx-geo-detail-section">
        <h4>Sources</h4>
        <div class="pplx-geo-detail-sources">${{sources.map((u, i) => `<a href="${{_escapeHtml(u)}}" target="_blank" rel="noopener">[${{i+1}}] ${{_escapeHtml(u)}}</a>`).join('')}}</div>
      </div>` : ''}}
    `;
    bd.classList.add('open');
  }};

  window.pplxGeoDetailClose = function() {{
    const bd = document.getElementById('pplxGeoDetailBackdrop');
    if (bd) bd.classList.remove('open');
  }};

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
      const bd = document.getElementById('pplxGeoDetailBackdrop');
      if (bd && bd.classList.contains('open')) window.pplxGeoDetailClose();
    }}
  }});

  /**
   * Wrap la fonction loadPplxGeoData existante pour :
   *  1. Stocker les risques dans window._pplxGeoRisks
   *  2. Ajouter un bouton "Voir l article" sur chaque carte rendue
   */
  function _wrapGeoLoader() {{
    const orig = window.loadPplxGeoData;
    if (typeof orig !== 'function') {{
      console.warn('[PPLX-GEO-DETAIL] loadPplxGeoData absent, retry dans 1s');
      setTimeout(_wrapGeoLoader, 1000);
      return;
    }}
    if (orig._pplxGeoDetailWrapped) return;

    window.loadPplxGeoData = async function(...args) {{
      const result = await orig.apply(this, args);
      // Apres render, recuperer les risques via fetch direct pour les stocker
      try {{
        const res = await fetch('/api/pplx/geo');
        const data = await res.json();
        if (data && data.available && Array.isArray(data.risks)) {{
          window._pplxGeoRisks = data.risks;
          _injectDetailButtons();
        }}
      }} catch (e) {{
        console.warn('[PPLX-GEO-DETAIL] fetch risks failed', e);
      }}
      return result;
    }};
    window.loadPplxGeoData._pplxGeoDetailWrapped = true;
    console.log('[PPLX-GEO-DETAIL] loadPplxGeoData wrappe');

    // Premier render : declenche maintenant si la section existe deja
    if (document.querySelector('#pplxGeoSection, [data-pplx-geo], .pplx-geo-panel')) {{
      window.loadPplxGeoData();
    }}
  }}

  function _injectDetailButtons() {{
    const risks = window._pplxGeoRisks || [];
    if (risks.length === 0) return;

    // Trouve toutes les cartes risque - le selecteur depend du rendu existant.
    // Strategie : on cherche chaque element contenant le risk_id dans son texte
    // ou ayant un data-risk-id.
    risks.forEach(risk => {{
      const rid = risk.risk_id || risk.id;
      if (!rid) return;

      // Tentative 1 : carte avec data-risk-id
      let card = document.querySelector(`[data-risk-id="${{CSS.escape(rid)}}"]`);

      // Tentative 2 : chercher par titre dans toutes les cards potentielles
      if (!card && risk.title) {{
        const cards = document.querySelectorAll('#pplxGeoSection .risk-card, #pplxGeoSection > div > div, [data-pplx-geo] > div > div');
        for (const c of cards) {{
          if (c.textContent && c.textContent.includes(risk.title.slice(0, 40))) {{
            card = c;
            break;
          }}
        }}
      }}

      // Tentative 3 : tres large, n importe quel div contenant le titre
      if (!card && risk.title) {{
        const all = document.querySelectorAll('div, article');
        for (const c of all) {{
          if (c.dataset.geoBtnInjected) continue;
          if (c.children.length > 1 && c.textContent.includes(risk.title.slice(0, 40))) {{
            // Verifie que c est bien une carte (pas le doc entier)
            if (c.offsetHeight < 600 && c.offsetWidth < 900) {{
              card = c;
              break;
            }}
          }}
        }}
      }}

      if (!card) return;
      if (card.dataset.geoBtnInjected === '1') return;

      const btn = document.createElement('button');
      btn.className = 'pplx-geo-detail-btn';
      btn.textContent = 'Voir l\\'article complet';
      btn.addEventListener('click', (e) => {{
        e.stopPropagation();
        window.pplxGeoDetailOpen(rid);
      }});
      card.appendChild(btn);
      card.dataset.geoBtnInjected = '1';
    }});
  }}

  /**
   * Deplace la section #pplxGeoSection en haut de la page MACRO US
   * (tab-macro ou son equivalent), juste apres le titre/header.
   */
  function _moveGeoToTop() {{
    const section = document.querySelector('#pplxGeoSection, [data-pplx-geo-panel]');
    if (!section) {{
      // Pas encore rendue, retry
      return false;
    }}
    if (section.dataset.movedTop === '1') return true;

    // Container cible : tab-macro
    const macroTab = document.getElementById('tab-macro') || document.querySelector('[data-tab="macro"], .tab-macro');
    if (!macroTab) {{
      console.warn('[PPLX-GEO-DETAIL] tab-macro introuvable');
      return false;
    }}

    // Insertion : juste apres le 1er enfant (titre/header) ou au tout debut
    // On cherche d abord un h2/h3 pour ne pas casser le titre principal
    const firstHeading = macroTab.querySelector(':scope > h1, :scope > h2, :scope > h3');
    if (firstHeading && firstHeading.nextSibling) {{
      macroTab.insertBefore(section, firstHeading.nextSibling);
    }} else {{
      macroTab.insertBefore(section, macroTab.firstChild);
    }}
    section.dataset.movedTop = '1';
    console.log('[PPLX-GEO-DETAIL] Section geo deplacee en haut de tab-macro');
    return true;
  }}

  // Observer pour deplacer la section + injecter les boutons des qu elle apparait
  function _startObserver() {{
    // Tente immediatement
    _moveGeoToTop();
    _wrapGeoLoader();

    const obs = new MutationObserver(() => {{
      _moveGeoToTop();
      _injectDetailButtons();
    }});
    obs.observe(document.body, {{ childList: true, subtree: true }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', _startObserver);
  }} else {{
    _startObserver();
  }}

  console.log('[PPLX-GEO-DETAIL] Module initialise');
}})();
/* === END {MARKER_JS} === */
"""


def patch_index():
    if not INDEX.exists():
        return False, "index.html introuvable"
    text = INDEX.read_text(encoding="utf-8-sig")

    css_done = MARKER_CSS in text
    html_done = MARKER_HTML in text
    if css_done and html_done:
        return True, "deja patche (CSS+HTML)"

    bak = INDEX.with_name(INDEX.name + f".bak_geodetail_{TS}")
    bak.write_text(text, encoding="utf-8")

    if not css_done:
        if "</style>" in text:
            text = text.replace("</style>", CSS_BLOCK + "\n</style>", 1)
        else:
            text = text.replace("</head>", f"<style>\n{CSS_BLOCK}\n</style>\n</head>", 1)

    if not html_done:
        if "</body>" in text:
            text = text.replace("</body>", HTML_MODAL + "\n</body>", 1)
        else:
            text += "\n" + HTML_MODAL + "\n"

    INDEX.write_text(text, encoding="utf-8", newline="\n")
    return True, "patch CSS+HTML applique"


def patch_app_js():
    if not APP_JS.exists():
        return False, "app.js introuvable"
    text = APP_JS.read_text(encoding="utf-8-sig")
    if MARKER_JS in text:
        return True, "deja patche (JS)"

    bak = APP_JS.with_name(APP_JS.name + f".bak_geodetail_{TS}")
    bak.write_text(text, encoding="utf-8")

    if not text.endswith("\n"):
        text += "\n"
    text += JS_BLOCK + "\n"
    APP_JS.write_text(text, encoding="utf-8", newline="\n")
    return True, "patch JS applique"


def main():
    print(f"=== Patch Geo: move panel + detail modal - TS={TS} ===\n")
    ok1, msg1 = patch_index()
    print(f"[INDEX] {'OK' if ok1 else 'KO'} : {msg1}")
    ok2, msg2 = patch_app_js()
    print(f"[APP.JS] {'OK' if ok2 else 'KO'} : {msg2}")

    print("\n=== Validation ===")
    if INDEX.exists():
        t = INDEX.read_text(encoding="utf-8")
        print(f"  index.html : CSS={MARKER_CSS in t}  HTML={MARKER_HTML in t}")
    if APP_JS.exists():
        t = APP_JS.read_text(encoding="utf-8")
        print(f"  app.js     : JS={MARKER_JS in t}")

    if ok1 and ok2:
        print("\n[OK] Patches appliques. Rafraichis le navigateur (Ctrl+Shift+R).")
        print("    1. Section geo doit remonter en haut de l'onglet MACRO US")
        print("    2. Chaque carte risque doit avoir un bouton 'Voir l'article complet'")
        print("    3. Le bouton ouvre un modal avec narrative + catalysts + mechanism + sources")


if __name__ == "__main__":
    main()
