# -*- coding: utf-8 -*-
"""
Fix forme Shadow Variants (Jalon 9.6 polish) :
  1. Memo IA parasite : retire les boutons "Memo IA" injectes par un autre
     code dans la card via MutationObserver de nettoyage local.
  2. Bouton Rafraichir : style inline propre (cadre + hover).
  3. Tooltip RECO : title sur le <th> + abreviations expliquees.
  4. n_cycles dans meta : ajoute "| sur X cycles".
  5. Timestamp derniere maj : affiche created_at de la row.
  6. Description variant : title attribute (tooltip survol) sur nom.

Idempotent via marker [SHADOW_UI_V1_POLISH].
Remplace COMPLETEMENT le bloc IIFE shadow_variants (de [SHADOW_UI_V1] BEGIN
a [SHADOW_UI_V1] END) par une version polish.

Egalement remplace dans index.html le <th>RECO</th> par version avec tooltip
ET ajoute le bouton Rafraichir style.
"""
import os
import re
import shutil
from datetime import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

MARK_POLISH = "/* [SHADOW_UI_V1_POLISH] */"
MARK_HTML_POLISH = "<!-- [SHADOW_UI_V1_POLISH] -->"
MARK_JS_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_JS_END = "/* [SHADOW_UI_V1] END */"

# -----------------------------------------------------------------------------
# Nouveau bloc JS complet (remplace IIFE existant)
# -----------------------------------------------------------------------------
JS_NEW = r"""/* [SHADOW_UI_V1] BEGIN */
/* [SHADOW_UI_V1_POLISH] */
(function(){
  function fmtPct(v){
    if (v === null || v === undefined || isNaN(v)) return "-";
    var sign = v > 0 ? "+" : "";
    return sign + Number(v).toFixed(3).replace(".",",") + "%";
  }
  function fmtNum(v, dec){
    if (v === null || v === undefined || isNaN(v)) return "-";
    return Number(v).toFixed(dec === undefined ? 2 : dec).replace(".",",");
  }
  function recoBadge(reco){
    var color = "#888"; var bg = "rgba(136,136,136,0.15)";
    var label = reco || "neutral";
    if (reco === "champion"){ color = "#22c55e"; bg = "rgba(34,197,94,0.15)"; }
    else if (reco === "reject"){ color = "#ef4444"; bg = "rgba(239,68,68,0.15)"; }
    return '<span class="shadow-reco-badge" style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:'+color+';background:'+bg+';">'+label+'</span>';
  }
  function esc(s){
    if (s === null || s === undefined) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }

  function cleanupParasites(){
    var card = document.getElementById("shadow-variants-card");
    if (!card) return;
    // Retire tout bouton ou lien externe injecte dans la card qui n'a pas notre classe shadow-*
    card.querySelectorAll("button, a").forEach(function(el){
      if (el.id === "shadow-refresh-btn") return;
      if (el.classList && (el.classList.contains("shadow-reco-badge") || el.classList.contains("shadow-keep"))) return;
      // Si bouton hors de notre header -> suppression
      if (el.closest("#shadow-variants-table") || (el.textContent && /memo/i.test(el.textContent))){
        el.remove();
      }
    });
  }

  async function renderShadowVariants(){
    var meta = document.getElementById("shadow-variants-meta");
    var tbody = document.getElementById("shadow-variants-tbody");
    if (!meta || !tbody) return;
    meta.textContent = "Chargement...";
    tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Chargement...</td></tr>';
    try {
      var perf = await apiFetch("/api/shadow/perf-rolling?window=30");
      if (!perf || !perf.success){
        meta.textContent = "Erreur API perf-rolling";
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Erreur : '+(perf && perf.error ? perf.error : "inconnu")+'</td></tr>';
        return;
      }
      var rows = perf.rows || [];
      var nCycles = rows[0] && rows[0].n_cycles !== undefined ? rows[0].n_cycles : "?";
      var createdAt = rows[0] && rows[0].created_at ? rows[0].created_at : "-";
      meta.innerHTML = 'Fenetre <strong>'+perf.window_days+'j</strong> | as_of_day=<strong>'+perf.as_of_day+'</strong> | <strong>'+rows.length+'</strong> variants | sur <strong>'+nCycles+'</strong> cycles | derniere maj '+esc(createdAt);
      if (rows.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Aucune donnee</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r){
        var desc = r.description || "";
        html += '<tr style="border-bottom:1px solid var(--border-color,#333);">';
        html += '<td style="padding:6px 8px;font-weight:600;" title="'+esc(desc)+'">'+esc(r.variant_name || r.variant_id || "?")+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.return_variant_pct)+'</td>';
        var deltaColor = r.delta_pct > 0 ? "#22c55e" : (r.delta_pct < 0 ? "#ef4444" : "inherit");
        html += '<td style="padding:6px 8px;text-align:right;color:'+deltaColor+';font-weight:600;">'+fmtPct(r.delta_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtNum(r.sharpe_variant,2)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.max_dd_variant_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+(r.n_orders_variant !== undefined && r.n_orders_variant !== null ? r.n_orders_variant : "-")+'</td>';
        html += '<td style="padding:6px 8px;text-align:center;">'+recoBadge(r.recommendation)+'</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
      cleanupParasites();
      setTimeout(cleanupParasites, 200);
      setTimeout(cleanupParasites, 1000);
    } catch(e){
      meta.textContent = "Erreur reseau";
      tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;color:#ef4444;">Exception : '+(e && e.message ? e.message : String(e))+'</td></tr>';
    }
  }
  window.renderShadowVariants = renderShadowVariants;

  function bindShadowUI(){
    var btn = document.getElementById("shadow-refresh-btn");
    if (btn && !btn.dataset.shadowBound){
      btn.dataset.shadowBound = "1";
      btn.addEventListener("click", renderShadowVariants);
    }
    var tabLink = document.querySelector('a[data-tab="backtest"]');
    if (tabLink && !tabLink.dataset.shadowBound){
      tabLink.dataset.shadowBound = "1";
      tabLink.addEventListener("click", function(){ setTimeout(renderShadowVariants, 120); });
    }
    /* [SHADOW_UI_V1_FIX_WAIT_TOKEN] */
    function tryInitialLoad(attemptsLeft){
      if (typeof state === "undefined" || !state || !state.token){
        if (attemptsLeft > 0){ setTimeout(function(){ tryInitialLoad(attemptsLeft - 1); }, 500); }
        return;
      }
      if (document.querySelector("#tab-backtest.active") || (location.hash === "#backtest")){
        renderShadowVariants();
      }
    }
    tryInitialLoad(10);

    // MutationObserver pour rejouer cleanup si un autre code injecte tardivement
    var card = document.getElementById("shadow-variants-card");
    if (card && !card.dataset.shadowObserver){
      card.dataset.shadowObserver = "1";
      var obs = new MutationObserver(function(muts){
        for (var i=0; i<muts.length; i++){
          var m = muts[i];
          for (var j=0; j<m.addedNodes.length; j++){
            var n = m.addedNodes[j];
            if (n.nodeType === 1){
              var tag = n.tagName;
              if ((tag === "BUTTON" || tag === "A") && n.id !== "shadow-refresh-btn"){
                if (n.textContent && /memo/i.test(n.textContent)){ n.remove(); }
              }
            }
          }
        }
      });
      obs.observe(card, { childList: true, subtree: true });
    }
  }
  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", bindShadowUI);
  } else {
    bindShadowUI();
  }
})();
/* [SHADOW_UI_V1] END */"""

# -----------------------------------------------------------------------------
# Patch JS
# -----------------------------------------------------------------------------
def patch_js():
    with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_POLISH in src:
        print("[SKIP] JS polish marker deja present")
        return False
    # Trouver et remplacer le bloc complet [SHADOW_UI_V1] BEGIN ... END
    pat = re.compile(
        re.escape(MARK_JS_BEGIN) + r".*?" + re.escape(MARK_JS_END),
        re.DOTALL
    )
    if not pat.search(src):
        print("[ERR] bloc [SHADOW_UI_V1] BEGIN ... END introuvable dans app.js")
        return False
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK] JS ->", bak)
    new = pat.sub(JS_NEW, src, count=1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    print("[INFO] marker polish present:", new.count(MARK_POLISH))
    return True

# -----------------------------------------------------------------------------
# Patch HTML : remplace <th>Reco</th> + bouton Rafraichir style
# -----------------------------------------------------------------------------
def patch_html():
    with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    if MARK_HTML_POLISH in src:
        print("[SKIP] HTML polish marker deja present")
        return False

    bak = HTML + ".bak." + TS
    shutil.copy2(HTML, bak)
    print("[BAK] HTML ->", bak)

    # 1. <th> Reco -> tooltip
    OLD_TH = '<th style="padding:6px 8px;text-align:center;">Reco</th>'
    NEW_TH = '<th style="padding:6px 8px;text-align:center;" title="champion : delta > +2 pts et Sharpe > prod | reject : delta < -1 pt | sinon neutral">Reco</th>'
    if OLD_TH in src:
        src = src.replace(OLD_TH, NEW_TH, 1)
        print("[OK] <th>Reco</th> tooltip ajoute")
    else:
        print("[WARN] <th>Reco</th> introuvable - skip")

    # 2. Bouton Rafraichir : style inline propre
    OLD_BTN = '<button id="shadow-refresh-btn" class="pplx-refresh-btn" type="button">Rafraichir</button>'
    NEW_BTN = ('<button id="shadow-refresh-btn" class="pplx-refresh-btn shadow-keep" type="button" '
               'style="padding:6px 14px;border:1px solid var(--border-color,#555);'
               'background:transparent;color:inherit;border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;">'
               'Rafraichir</button>')
    if OLD_BTN in src:
        src = src.replace(OLD_BTN, NEW_BTN, 1)
        print("[OK] bouton Rafraichir style applique")
    else:
        print("[WARN] bouton Rafraichir introuvable - skip")

    # 3. Marqueur polish
    # Inserer le marker au debut du bloc shadow-variants-card pour idempotence
    OLD_CARD = '<div id="shadow-variants-card"'
    NEW_CARD = MARK_HTML_POLISH + '\n        <div id="shadow-variants-card"'
    if OLD_CARD in src:
        src = src.replace(OLD_CARD, NEW_CARD, 1)
        print("[OK] marker polish HTML insere")

    with open(HTML, "w", encoding="utf-8", newline="") as f:
        f.write(src)
    return True

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("FIX FORME SHADOW UI V1 (polish)")
    print("=" * 70)
    j = patch_js()
    print()
    h = patch_html()
    print()
    print("JS   patched :", j)
    print("HTML patched :", h)
    print()
    print("Apres :")
    print("  Ctrl+Shift+R sur navigateur, tab Backtest")
    print("  Verifier : pas de 'Memo IA' a cote de prod-neutral,")
    print("             bouton Rafraichir avec cadre,")
    print("             survol 'tight_conv' montre la description,")
    print("             meta ligne 2 : 'sur 14 cycles | derniere maj 2026-06-12 ...'")
    print("DONE")
