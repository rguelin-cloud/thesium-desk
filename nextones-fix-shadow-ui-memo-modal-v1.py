# -*- coding: utf-8 -*-
"""
Jalon 9.5b UI : badge cliquable -> modal avec memo IA.

Modifie app.js :
  - recoBadge() : badge devient cliquable (cursor pointer + data-row-id)
  - Le forEach passe les rows complets via dataset
  - Ajout fonction openShadowMemoModal(row) qui affiche dans une modal
  - Marker [SHADOW_UI_V1_MEMO_MODAL]

Idempotent.
"""
import os
import re
import shutil
from datetime import datetime

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_MEMO = "/* [SHADOW_UI_V1_MEMO_MODAL] */"
MARK_JS_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_JS_END = "/* [SHADOW_UI_V1] END */"

# Nouveau bloc IIFE complet (avec memo modal integre)
JS_NEW = r"""/* [SHADOW_UI_V1] BEGIN */
/* [SHADOW_UI_V1_POLISH] */
/* [SHADOW_UI_V1_MEMO_MODAL] */
(function(){
  var shadowRowsCache = {};

  function fmtPct(v){
    if (v === null || v === undefined || isNaN(v)) return "-";
    var sign = v > 0 ? "+" : "";
    return sign + Number(v).toFixed(3).replace(".",",") + "%";
  }
  function fmtNum(v, dec){
    if (v === null || v === undefined || isNaN(v)) return "-";
    return Number(v).toFixed(dec === undefined ? 2 : dec).replace(".",",");
  }
  function esc(s){
    if (s === null || s === undefined) return "";
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function recoBadge(reco, rowId, hasMemo){
    var color = "#888"; var bg = "rgba(136,136,136,0.15)";
    var label = reco || "neutral";
    if (reco === "champion"){ color = "#22c55e"; bg = "rgba(34,197,94,0.15)"; }
    else if (reco === "reject"){ color = "#ef4444"; bg = "rgba(239,68,68,0.15)"; }
    var dot = hasMemo ? ' <span style="opacity:0.7;font-size:9px;">[Memo]</span>' : "";
    var tip = hasMemo ? "Cliquer pour lire le memo IA" : "Pas de memo IA generee";
    var cursor = hasMemo ? "pointer" : "default";
    return '<span class="shadow-reco-badge" data-row-id="'+rowId+'" title="'+esc(tip)+'" style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:'+color+';background:'+bg+';cursor:'+cursor+';">'+label+dot+'</span>';
  }

  function cleanupParasites(){
    var card = document.getElementById("shadow-variants-card");
    if (!card) return;
    card.querySelectorAll("button, a").forEach(function(el){
      if (el.id === "shadow-refresh-btn") return;
      if (el.classList && (el.classList.contains("shadow-reco-badge") || el.classList.contains("shadow-keep"))) return;
      if (el.closest("#shadow-variants-table") || (el.textContent && /memo/i.test(el.textContent))){
        el.remove();
      }
    });
  }

  function ensureModal(){
    var m = document.getElementById("shadow-memo-modal");
    if (m) return m;
    m = document.createElement("div");
    m.id = "shadow-memo-modal";
    m.style.cssText = "display:none;position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.6);z-index:9999;justify-content:center;align-items:center;";
    m.innerHTML = (
      '<div id="shadow-memo-modal-box" class="shadow-keep" style="background:var(--bg-card,#1a1a1f);color:var(--text-primary,#eee);max-width:720px;width:90%;max-height:85vh;overflow-y:auto;border-radius:12px;padding:24px;box-shadow:0 8px 40px rgba(0,0,0,0.5);">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">'
      + '<h3 id="shadow-memo-modal-title" style="margin:0;">Memo IA</h3>'
      + '<button id="shadow-memo-modal-close" class="shadow-keep" style="background:transparent;border:1px solid var(--border-color,#555);color:inherit;padding:4px 12px;border-radius:6px;cursor:pointer;">Fermer</button>'
      + '</div>'
      + '<div id="shadow-memo-modal-meta" style="font-size:11px;opacity:0.65;margin-bottom:12px;"></div>'
      + '<pre id="shadow-memo-modal-body" style="white-space:pre-wrap;word-wrap:break-word;font-family:inherit;font-size:13px;line-height:1.55;margin:0;background:rgba(255,255,255,0.03);padding:14px;border-radius:8px;"></pre>'
      + '</div>'
    );
    document.body.appendChild(m);
    m.addEventListener("click", function(ev){
      if (ev.target === m) closeModal();
    });
    document.getElementById("shadow-memo-modal-close").addEventListener("click", closeModal);
    document.addEventListener("keydown", function(ev){
      if (ev.key === "Escape" && m.style.display === "flex") closeModal();
    });
    return m;
  }
  function closeModal(){
    var m = document.getElementById("shadow-memo-modal");
    if (m) m.style.display = "none";
  }
  function openShadowMemoModal(row){
    if (!row) return;
    var m = ensureModal();
    document.getElementById("shadow-memo-modal-title").textContent =
      "Memo IA - " + (row.variant_name || ("variant " + row.variant_id));
    var metaParts = [];
    if (row.recommendation) metaParts.push("Reco : " + row.recommendation);
    if (row.memo_source) metaParts.push("Source : " + row.memo_source);
    if (row.memo_generated_at) metaParts.push("Genere le " + row.memo_generated_at);
    if (row.window_days) metaParts.push("Fenetre " + row.window_days + "j");
    document.getElementById("shadow-memo-modal-meta").textContent = metaParts.join(" | ");
    var body = row.recommendation_memo || "(Aucun memo genere - lancer shadow_memo_generator.py)";
    document.getElementById("shadow-memo-modal-body").textContent = body;
    m.style.display = "flex";
  }
  window.openShadowMemoModal = openShadowMemoModal;

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
      shadowRowsCache = {};
      var nCycles = rows[0] && rows[0].n_cycles !== undefined ? rows[0].n_cycles : "?";
      var createdAt = rows[0] && rows[0].created_at ? rows[0].created_at : "-";
      meta.innerHTML = 'Fenetre <strong>'+perf.window_days+'j</strong> | as_of_day=<strong>'+perf.as_of_day+'</strong> | <strong>'+rows.length+'</strong> variants | sur <strong>'+nCycles+'</strong> cycles | derniere maj '+esc(createdAt);
      if (rows.length === 0){
        tbody.innerHTML = '<tr><td colspan="7" style="padding:12px;text-align:center;opacity:0.6;">Aucune donnee</td></tr>';
        return;
      }
      var html = "";
      rows.forEach(function(r){
        shadowRowsCache[r.id] = r;
        var desc = r.description || "";
        var hasMemo = !!(r.recommendation_memo);
        html += '<tr style="border-bottom:1px solid var(--border-color,#333);">';
        html += '<td style="padding:6px 8px;font-weight:600;" title="'+esc(desc)+'">'+esc(r.variant_name || r.variant_id || "?")+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.return_variant_pct)+'</td>';
        var deltaColor = r.delta_pct > 0 ? "#22c55e" : (r.delta_pct < 0 ? "#ef4444" : "inherit");
        html += '<td style="padding:6px 8px;text-align:right;color:'+deltaColor+';font-weight:600;">'+fmtPct(r.delta_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtNum(r.sharpe_variant,2)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+fmtPct(r.max_dd_variant_pct)+'</td>';
        html += '<td style="padding:6px 8px;text-align:right;">'+(r.n_orders_variant !== undefined && r.n_orders_variant !== null ? r.n_orders_variant : "-")+'</td>';
        html += '<td style="padding:6px 8px;text-align:center;">'+recoBadge(r.recommendation, r.id, hasMemo)+'</td>';
        html += '</tr>';
      });
      tbody.innerHTML = html;
      cleanupParasites();
      setTimeout(cleanupParasites, 200);
      setTimeout(cleanupParasites, 1000);

      // Click handlers sur badges
      tbody.querySelectorAll(".shadow-reco-badge").forEach(function(b){
        b.addEventListener("click", function(){
          var rid = b.getAttribute("data-row-id");
          var row = shadowRowsCache[rid];
          if (row && row.recommendation_memo){
            openShadowMemoModal(row);
          }
        });
      });
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

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

if MARK_MEMO in src:
    print("[SKIP] marker memo modal deja present")
else:
    pat = re.compile(
        re.escape(MARK_JS_BEGIN) + r".*?" + re.escape(MARK_JS_END),
        re.DOTALL
    )
    if not pat.search(src):
        print("[ERR] bloc [SHADOW_UI_V1] BEGIN ... END introuvable")
    else:
        bak = JS + ".bak." + TS
        shutil.copy2(JS, bak)
        print("[BAK]", bak)
        new = pat.sub(JS_NEW, src, count=1)
        with open(JS, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
        print("[INFO] marker memo modal :", new.count(MARK_MEMO))

print()
print("Next : Ctrl+Shift+R sur navigateur, tab Backtest")
print("DONE")
