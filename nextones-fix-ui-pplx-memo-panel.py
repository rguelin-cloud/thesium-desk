# -*- coding: utf-8 -*-
"""
Patch UI Memo IA : injecte le modal global + CSS + JS dans index.html et app.js.
Le bouton "Memo IA" sera injecte dynamiquement par JS dans chaque ligne du portfolio
(plus simple et plus robuste qu'un patch HTML statique sur des tableaux dynamiques).

Idempotent :
  - HTML : marker [PPLX_MEMO_MODAL_HTML_V1]
  - CSS  : marker [PPLX_MEMO_MODAL_CSS_V1]
  - JS   : marker [PPLX_MEMO_JS_V1]
"""
import sys
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
INDEX = ROOT / "index.html"
APP_JS = ROOT / "app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARKER_HTML = "[PPLX_MEMO_MODAL_HTML_V1]"
MARKER_CSS = "[PPLX_MEMO_MODAL_CSS_V1]"
MARKER_JS = "[PPLX_MEMO_JS_V1]"


CSS_BLOCK = f"""
/* === {MARKER_CSS} : Modal Memo IA Perplexity === */
.pplx-memo-backdrop {{
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.55);
  z-index: 9998;
  display: none;
  align-items: center; justify-content: center;
  backdrop-filter: blur(2px);
}}
.pplx-memo-backdrop.open {{ display: flex; }}
.pplx-memo-modal {{
  background: var(--color-surface, #1a1d24);
  color: var(--color-text, #e7eaf0);
  border: 1px solid var(--color-border, #2a2f3a);
  border-radius: 12px;
  width: min(720px, 92vw);
  max-height: 88vh;
  overflow-y: auto;
  padding: 22px 26px 26px;
  box-shadow: 0 24px 60px rgba(0,0,0,0.6);
  position: relative;
}}
.pplx-memo-modal h3 {{
  margin: 0 0 6px; font-size: 18px;
}}
.pplx-memo-modal .pplx-memo-close {{
  position: absolute; top: 12px; right: 14px;
  background: transparent; border: none; color: var(--color-text);
  font-size: 22px; cursor: pointer; line-height: 1;
  opacity: 0.7;
}}
.pplx-memo-modal .pplx-memo-close:hover {{ opacity: 1; }}
.pplx-memo-header-row {{
  display: flex; align-items: center; gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}}
.pplx-memo-stance {{
  font-size: 12px; font-weight: 600;
  padding: 3px 10px; border-radius: 12px;
  text-transform: uppercase; letter-spacing: 0.5px;
}}
.pplx-memo-stance.bullish {{ background: #1f6b3a; color: #d6f5dd; }}
.pplx-memo-stance.neutral {{ background: #5a5a2a; color: #f5f0d6; }}
.pplx-memo-stance.bearish {{ background: #7a2a2a; color: #f5d6d6; }}
.pplx-memo-confidence {{
  font-size: 12px; color: var(--color-text-muted, #9aa3b2);
}}
.pplx-memo-horizon {{
  font-size: 11px; color: var(--color-text-muted);
  background: rgba(255,255,255,0.05);
  padding: 2px 8px; border-radius: 8px;
}}
.pplx-memo-section {{ margin-top: 14px; }}
.pplx-memo-section h4 {{
  font-size: 12px; text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-text-muted);
  margin: 0 0 6px;
}}
.pplx-memo-section p {{ margin: 0; font-size: 14px; line-height: 1.45; }}
.pplx-memo-section ul {{ margin: 0; padding-left: 20px; }}
.pplx-memo-section li {{
  font-size: 13px; line-height: 1.45;
  margin-bottom: 5px;
}}
.pplx-memo-meta {{
  margin-top: 18px; padding-top: 12px;
  border-top: 1px solid var(--color-border);
  font-size: 11px; color: var(--color-text-muted);
  display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center;
}}
.pplx-memo-citations {{
  margin-top: 8px;
  font-size: 11px;
}}
.pplx-memo-citations a {{
  color: var(--color-primary, #2bb8a8);
  text-decoration: none;
  margin-right: 8px;
}}
.pplx-memo-citations a:hover {{ text-decoration: underline; }}
.pplx-memo-loading {{
  display: flex; align-items: center; gap: 10px;
  padding: 30px 0; color: var(--color-text-muted); font-size: 13px;
}}
.pplx-memo-loading::before {{
  content: ""; width: 14px; height: 14px;
  border: 2px solid var(--color-primary); border-top-color: transparent;
  border-radius: 50%;
  animation: pplxSpin 0.9s linear infinite;
}}
@keyframes pplxSpin {{ to {{ transform: rotate(360deg); }} }}
.pplx-memo-error {{
  padding: 16px; background: rgba(200,60,60,0.1);
  border-radius: 8px; color: #f5a8a8;
  font-size: 13px;
}}
.pplx-memo-actions {{
  display: flex; gap: 8px; margin-top: 16px;
}}
.pplx-memo-btn {{
  background: var(--color-primary, #2bb8a8);
  border: none; color: white;
  padding: 7px 14px; border-radius: 6px;
  font-size: 12px; cursor: pointer;
  font-weight: 500;
}}
.pplx-memo-btn:hover {{ filter: brightness(1.1); }}
.pplx-memo-btn.secondary {{
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text);
}}

/* Bouton dans la ligne du portfolio */
.pplx-memo-trigger {{
  background: transparent;
  border: 1px solid var(--color-border, #2a2f3a);
  color: var(--color-text-muted, #9aa3b2);
  padding: 3px 8px;
  font-size: 11px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex; align-items: center; gap: 4px;
  transition: all 0.15s;
}}
.pplx-memo-trigger:hover {{
  background: var(--color-primary, #2bb8a8);
  color: white;
  border-color: var(--color-primary, #2bb8a8);
}}
/* === END {MARKER_CSS} === */
"""


HTML_BLOCK = f"""
<!-- {MARKER_HTML} : Modal Memo IA (global, injecte une seule fois) -->
<div id="pplxMemoBackdrop" class="pplx-memo-backdrop" onclick="if(event.target===this)pplxMemoClose()">
  <div class="pplx-memo-modal" role="dialog" aria-modal="true" aria-labelledby="pplxMemoTitle">
    <button class="pplx-memo-close" onclick="pplxMemoClose()" aria-label="Fermer">×</button>
    <div id="pplxMemoBody">
      <div class="pplx-memo-loading">Chargement du memo IA…</div>
    </div>
  </div>
</div>
<!-- END {MARKER_HTML} -->
"""


JS_BLOCK = f"""
/* === {MARKER_JS} : MemoAgent UI (modal + injection bouton) === */
(function() {{
  if (window.pplxMemoOpen) {{ return; }}  // dejà injecte

  // Etat du modal courant
  let _currentSymbol = null;

  function _escapeHtml(s) {{
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
  }}

  function _fmtTs(iso) {{
    if (!iso) return '';
    try {{
      const d = new Date(iso);
      return d.toLocaleString('fr-FR', {{ day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }});
    }} catch (e) {{ return iso; }}
  }}

  function _renderMemo(data) {{
    const body = document.getElementById('pplxMemoBody');
    if (!body) return;
    if (!data || !data.available) {{
      body.innerHTML = `<div class="pplx-memo-error">Memo indisponible : ${{_escapeHtml((data && data.error) || 'erreur inconnue')}}</div>
        <div class="pplx-memo-actions">
          <button class="pplx-memo-btn" onclick="pplxMemoOpen('${{_currentSymbol}}', true)">Reessayer (force refresh)</button>
        </div>`;
      return;
    }}
    const p = data.payload || {{}};
    const stance = p.stance || 'neutral';
    const conf = (typeof p.confidence === 'number') ? `${{p.confidence}}/100` : '';
    const horizon = p.time_horizon ? `Horizon ${{p.time_horizon}}` : '';
    const bullets = Array.isArray(p.bullets) ? p.bullets : [];
    const risks = Array.isArray(p.risks) ? p.risks : [];
    const cats = Array.isArray(p.catalysts_upcoming) ? p.catalysts_upcoming : [];
    const cits = Array.isArray(data.citations) ? data.citations : [];
    const cached = data.cached ? `Cache ${{Math.round((data.age_seconds||0)/60)}} min` : 'Frais';

    body.innerHTML = `
      <h3 id="pplxMemoTitle">${{_escapeHtml(data.symbol)}} — ${{_escapeHtml(p.headline || '')}}</h3>
      <div class="pplx-memo-header-row">
        <span class="pplx-memo-stance ${{stance}}">${{stance}}</span>
        ${{conf ? `<span class="pplx-memo-confidence">Confiance ${{conf}}</span>` : ''}}
        ${{horizon ? `<span class="pplx-memo-horizon">${{_escapeHtml(horizon)}}</span>` : ''}}
      </div>
      <div class="pplx-memo-section">
        <h4>Synthese</h4>
        <p>${{_escapeHtml(p.summary || '')}}</p>
      </div>
      ${{bullets.length ? `
      <div class="pplx-memo-section">
        <h4>Observations cles</h4>
        <ul>${{bullets.map(b => `<li>${{_escapeHtml(b)}}</li>`).join('')}}</ul>
      </div>` : ''}}
      ${{risks.length ? `
      <div class="pplx-memo-section">
        <h4>Risques specifiques</h4>
        <ul>${{risks.map(r => `<li>${{_escapeHtml(r)}}</li>`).join('')}}</ul>
      </div>` : ''}}
      ${{cats.length ? `
      <div class="pplx-memo-section">
        <h4>Catalystes a venir</h4>
        <ul>${{cats.map(c => `<li>${{_escapeHtml(c)}}</li>`).join('')}}</ul>
      </div>` : ''}}
      <div class="pplx-memo-meta">
        <span>${{_escapeHtml(_fmtTs(data.generated_at))}}</span>
        <span>·</span>
        <span>${{_escapeHtml(data.model || '')}}</span>
        <span>·</span>
        <span>${{cached}}</span>
        ${{data.elapsed_s ? `<span>·</span><span>${{Number(data.elapsed_s).toFixed(1)}}s</span>` : ''}}
      </div>
      ${{cits.length ? `<div class="pplx-memo-citations">Sources : ${{cits.map((u, i) => `<a href="${{_escapeHtml(u)}}" target="_blank" rel="noopener">[${{i+1}}]</a>`).join('')}}</div>` : ''}}
      <div class="pplx-memo-actions">
        <button class="pplx-memo-btn secondary" onclick="pplxMemoOpen('${{_currentSymbol}}', true)">Rafraichir</button>
        <button class="pplx-memo-btn" onclick="pplxMemoClose()">Fermer</button>
      </div>
    `;
  }}

  window.pplxMemoOpen = async function(symbol, force) {{
    if (!symbol) return;
    _currentSymbol = symbol;
    const bd = document.getElementById('pplxMemoBackdrop');
    const body = document.getElementById('pplxMemoBody');
    if (!bd || !body) {{
      console.error('[PPLX-MEMO] Modal HTML absent');
      return;
    }}
    bd.classList.add('open');
    body.innerHTML = `<div class="pplx-memo-loading">Chargement du memo IA pour ${{_escapeHtml(symbol)}}…</div>`;
    try {{
      const url = `/api/pplx/memo?symbol=${{encodeURIComponent(symbol)}}${{force ? '&force=true' : ''}}`;
      const res = await fetch(url);
      const data = await res.json();
      _renderMemo(data);
    }} catch (e) {{
      body.innerHTML = `<div class="pplx-memo-error">Erreur reseau : ${{_escapeHtml(String(e))}}</div>`;
    }}
  }};

  window.pplxMemoClose = function() {{
    const bd = document.getElementById('pplxMemoBackdrop');
    if (bd) bd.classList.remove('open');
    _currentSymbol = null;
  }};

  // ESC pour fermer
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') {{
      const bd = document.getElementById('pplxMemoBackdrop');
      if (bd && bd.classList.contains('open')) pplxMemoClose();
    }}
  }});

  /**
   * Injection automatique des boutons "Memo IA" dans le tableau du portfolio.
   * Strategie : MutationObserver qui surveille les changements du DOM et ajoute
   * un bouton dans chaque ligne ayant un attribut data-symbol ou un .symbol-cell.
   * Repli : recherche par texte de la 1ere cellule (ticker en majuscule, 2-6 chars).
   */
  function _injectMemoButtons() {{
    // Cherche toutes les lignes <tr> du document
    const rows = document.querySelectorAll('tr');
    rows.forEach(row => {{
      if (row.dataset.memoInjected === '1') return;
      // Detection symbol : 1) data-symbol attr, 2) .symbol cell, 3) 1ere cellule
      let symbol = row.dataset.symbol || row.getAttribute('data-symbol');
      if (!symbol) {{
        const symCell = row.querySelector('[data-symbol], .symbol, .ticker, td.symbol-cell');
        if (symCell) symbol = symCell.dataset.symbol || symCell.textContent.trim();
      }}
      if (!symbol) {{
        // Repli : 1ere cellule, si elle ressemble a un ticker (2-8 chars, majuscules + maj/chiffres)
        const firstCell = row.querySelector('td');
        if (firstCell) {{
          const t = firstCell.textContent.trim();
          if (/^[A-Z]{{2,6}}(USDT|USD|EUR)?$/i.test(t) && t.length <= 10) symbol = t.toUpperCase();
        }}
      }}
      if (!symbol || symbol.length > 12) return;

      // Cherche un container pour le bouton : derniere cellule
      const cells = row.querySelectorAll('td');
      if (cells.length === 0) return;
      const lastCell = cells[cells.length - 1];

      // Cree le bouton
      const btn = document.createElement('button');
      btn.className = 'pplx-memo-trigger';
      btn.title = `Generer un memo IA pour ${{symbol}}`;
      btn.innerHTML = '<span>Memo IA</span>';
      btn.addEventListener('click', (e) => {{
        e.stopPropagation();
        window.pplxMemoOpen(symbol, false);
      }});
      lastCell.appendChild(btn);
      row.dataset.memoInjected = '1';
    }});
  }}

  // Lance l'injection au load + observer pour les ajouts dynamiques
  function _startInjection() {{
    _injectMemoButtons();
    const obs = new MutationObserver((mutations) => {{
      let shouldRun = false;
      for (const m of mutations) {{
        if (m.addedNodes.length > 0) {{ shouldRun = true; break; }}
      }}
      if (shouldRun) _injectMemoButtons();
    }});
    obs.observe(document.body, {{ childList: true, subtree: true }});
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', _startInjection);
  }} else {{
    _startInjection();
  }}

  console.log('[PPLX-MEMO] UI initialisee');
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

    bak = INDEX.with_name(INDEX.name + f".bak_memo_{TS}")
    bak.write_text(text, encoding="utf-8")

    # 1) Inject CSS dans <style> ou ajoute un <style> nouveau si pas trouve
    if not css_done:
        # Cherche </style> et insert avant
        if "</style>" in text:
            text = text.replace("</style>", CSS_BLOCK + "\n</style>", 1)
        else:
            # Inject un nouveau bloc style dans head
            text = text.replace("</head>", f"<style>\n{CSS_BLOCK}\n</style>\n</head>", 1)

    # 2) Inject HTML modal avant </body>
    if not html_done:
        if "</body>" in text:
            text = text.replace("</body>", HTML_BLOCK + "\n</body>", 1)
        else:
            text += "\n" + HTML_BLOCK + "\n"

    INDEX.write_text(text, encoding="utf-8", newline="\n")
    return True, "patch CSS+HTML applique"


def patch_app_js():
    if not APP_JS.exists():
        return False, "app.js introuvable"
    text = APP_JS.read_text(encoding="utf-8-sig")

    if MARKER_JS in text:
        return True, "deja patche (JS)"

    bak = APP_JS.with_name(APP_JS.name + f".bak_memo_{TS}")
    bak.write_text(text, encoding="utf-8")

    # Append en fin (le JS est auto-IIFE, s'execute au chargement)
    if not text.endswith("\n"):
        text += "\n"
    text += JS_BLOCK + "\n"
    APP_JS.write_text(text, encoding="utf-8", newline="\n")
    return True, "patch JS applique"


def main():
    print(f"=== Patch UI Memo IA - TS={TS} ===\n")

    ok1, msg1 = patch_index()
    print(f"[INDEX] {'OK' if ok1 else 'KO'} : {msg1}")
    ok2, msg2 = patch_app_js()
    print(f"[APP.JS] {'OK' if ok2 else 'KO'} : {msg2}")

    # Validation
    print("\n=== Validation ===")
    if INDEX.exists():
        t = INDEX.read_text(encoding="utf-8")
        print(f"  index.html : CSS={MARKER_CSS in t}  HTML={MARKER_HTML in t}")
    if APP_JS.exists():
        t = APP_JS.read_text(encoding="utf-8")
        print(f"  app.js     : JS={MARKER_JS in t}")

    if ok1 and ok2:
        print("\n[OK] Patches appliques. Rafraichis le navigateur (Ctrl+Shift+R).")
        print("    Un bouton 'Memo IA' apparaitra dans chaque ligne du portfolio.")
    else:
        print("\n[KO] Patch incomplet, voir messages ci-dessus.")


if __name__ == "__main__":
    main()
