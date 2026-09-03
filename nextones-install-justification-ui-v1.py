"""
Patch 5a/6 - UI Pending Approvals : justification + bouton Memo IA
===================================================================

Modifie app.js (racine ThesiumDesk) :

1) Enrichit le HTML de chaque row dans renderPendingApprovals() :
   - Nouvelle ligne "justification" full-width sous le grid (opacite 0.7, italique)
     -> conditionnelle : ne s'affiche que si o.justification present
   - Nouveau bouton "Memo IA" avant Execute (badge visuel si o.has_memo=1)

2) Ajoute openOrderMemoModal(order) + wire click sur .pa-memo-btn
   -> Reutilise ensureModal() du pattern SHADOW_UI (L7411)
   -> POST /api/orders/{id}/memo
   -> Cache local par order_id (evite spam pplx)

Markers C-style JS : /* [JUSTIFICATION_UI_V1] BEGIN */ ... /* END */
Idempotent (skip si marker present)
Backup app.js.bak.<TS>
"""
import os
import re
import shutil
import sys
import time

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
MARK_BEGIN = "/* [JUSTIFICATION_UI_V1] BEGIN */"
MARK_END = "/* [JUSTIFICATION_UI_V1] END */"
TS = time.strftime("%Y%m%d_%H%M%S")


# ---------- Ancien HTML template (L7103-L7126 exact) ----------
OLD_TEMPLATE = '''      list.innerHTML = orders.map(function(o) {
        var notional = (o.last_price && o.quantity) ? (o.last_price * o.quantity) : null;
        return '<div data-order-id="' + o.id + '" '
          + 'style="display:grid;grid-template-columns:60px 80px 1fr 110px 110px 140px 180px;'
          + 'gap:8px;align-items:center;padding:8px 10px;background:#0f1830;'
          + 'border:1px solid #232c47;border-radius:8px;font-size:12.5px;">'
          + '  <span style="font-weight:700;color:' + _sideColor(o.side) + ';text-transform:uppercase;">'
          + (o.side || "-") + '</span>'
          + '  <span style="font-weight:700;">' + (o.ticker || "?") + '</span>'
          + '  <span style="opacity:.75;font-size:11.5px;">#' + o.id + ' &middot; '
          +    'cycle ' + (o.cycle_id || "n/a") + ' &middot; ' + (o.created_at || "") + '</span>'
          + '  <span>Qty <b>' + _fmtQty(o.quantity) + '</b></span>'
          + '  <span>Px <b>' + _fmtPrice(o.last_price) + '</b></span>'
          + '  <span>Notional <b>' + (notional ? _fmtPrice(notional) : "-") + '</b></span>'
          + '  <span style="display:flex;gap:6px;justify-content:flex-end;">'
          + '    <button class="pa-exec-btn" data-id="' + o.id + '" '
          +      'style="background:#3ddc84;color:#0c1322;border:0;border-radius:6px;'
          +      'padding:5px 10px;font-weight:700;cursor:pointer;">Execute</button>'
          + '    <button class="pa-rej-btn" data-id="' + o.id + '" '
          +      'style="background:#ff6b6b;color:#0c1322;border:0;border-radius:6px;'
          +      'padding:5px 10px;font-weight:700;cursor:pointer;">Reject</button>'
          + '  </span>'
          + '</div>';
      }).join("");'''


NEW_TEMPLATE = '''      /* [JUSTIFICATION_UI_V1] BEGIN */
      list.innerHTML = orders.map(function(o) {
        var notional = (o.last_price && o.quantity) ? (o.last_price * o.quantity) : null;
        var hasJust = !!(o.justification);
        var hasMemo = !!(o.has_memo);
        var justBlock = hasJust
          ? ('<div style="grid-column:1/-1;margin-top:4px;padding:5px 8px;'
             + 'background:#0a1225;border-left:2px solid #4a7fbf;border-radius:4px;'
             + 'font-size:11.5px;font-style:italic;opacity:.85;line-height:1.4;">'
             + String(o.justification).replace(/</g,"&lt;").replace(/>/g,"&gt;")
             + '</div>')
          : '';
        var memoBadge = hasMemo ? ' &#9679;' : '';  /* bullet si memo deja genere */
        return '<div data-order-id="' + o.id + '" '
          + 'style="display:grid;grid-template-columns:60px 80px 1fr 110px 110px 140px 220px;'
          + 'gap:8px;align-items:center;padding:8px 10px;background:#0f1830;'
          + 'border:1px solid #232c47;border-radius:8px;font-size:12.5px;">'
          + '  <span style="font-weight:700;color:' + _sideColor(o.side) + ';text-transform:uppercase;">'
          + (o.side || "-") + '</span>'
          + '  <span style="font-weight:700;">' + (o.ticker || "?") + '</span>'
          + '  <span style="opacity:.75;font-size:11.5px;">#' + o.id + ' &middot; '
          +    'cycle ' + (o.cycle_id || "n/a") + ' &middot; ' + (o.created_at || "") + '</span>'
          + '  <span>Qty <b>' + _fmtQty(o.quantity) + '</b></span>'
          + '  <span>Px <b>' + _fmtPrice(o.last_price) + '</b></span>'
          + '  <span>Notional <b>' + (notional ? _fmtPrice(notional) : "-") + '</b></span>'
          + '  <span style="display:flex;gap:6px;justify-content:flex-end;">'
          + '    <button class="pa-memo-btn" data-id="' + o.id + '" '
          +      'title="Generer/voir memo IA" '
          +      'style="background:#3a4a6b;color:#dce3f5;border:0;border-radius:6px;'
          +      'padding:5px 8px;font-weight:600;cursor:pointer;font-size:11.5px;">'
          +      'Memo' + memoBadge + '</button>'
          + '    <button class="pa-exec-btn" data-id="' + o.id + '" '
          +      'style="background:#3ddc84;color:#0c1322;border:0;border-radius:6px;'
          +      'padding:5px 10px;font-weight:700;cursor:pointer;">Execute</button>'
          + '    <button class="pa-rej-btn" data-id="' + o.id + '" '
          +      'style="background:#ff6b6b;color:#0c1322;border:0;border-radius:6px;'
          +      'padding:5px 10px;font-weight:700;cursor:pointer;">Reject</button>'
          + '  </span>'
          + justBlock
          + '</div>';
      }).join("");
      /* [JUSTIFICATION_UI_V1] END */'''


# ---------- Ancien bloc listeners (L7128-L7137 exact) ----------
OLD_LISTENERS = '''      list.querySelectorAll(".pa-exec-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          _paExecute(btn.getAttribute("data-id"));
        });
      });
      list.querySelectorAll(".pa-rej-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          _paReject(btn.getAttribute("data-id"));
        });
      });'''


NEW_LISTENERS = '''      list.querySelectorAll(".pa-exec-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          _paExecute(btn.getAttribute("data-id"));
        });
      });
      list.querySelectorAll(".pa-rej-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          _paReject(btn.getAttribute("data-id"));
        });
      });
      /* [JUSTIFICATION_UI_V1] wire bouton Memo IA */
      list.querySelectorAll(".pa-memo-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          var oid = btn.getAttribute("data-id");
          var row = orders.find(function(x){ return String(x.id) === String(oid); });
          if (row) openOrderMemoModal(row);
        });
      });'''


# ---------- Nouveau bloc fonction openOrderMemoModal (a inserer avant window.renderPendingApprovals) ----------
MEMO_MODAL_FUNC = '''
  /* [JUSTIFICATION_UI_V1] BEGIN openOrderMemoModal */
  var _orderMemoCache = {};

  async function openOrderMemoModal(order) {
    var m = ensureModal();
    var oid = order && order.id;
    if (!oid) return;

    /* Header modal */
    var titleColor = _sideColor(order.side);
    var headerHtml = '<div style="padding:14px 18px;border-bottom:1px solid #232c47;">'
      + '<div style="font-size:11px;opacity:.6;text-transform:uppercase;letter-spacing:.5px;">Memo IA - ordre #' + oid + '</div>'
      + '<div style="font-size:18px;font-weight:700;margin-top:4px;">'
      + '<span style="color:' + titleColor + ';text-transform:uppercase;">' + (order.side || "-") + '</span> '
      + _fmtQty(order.quantity) + ' <b>' + (order.ticker || "?") + '</b>'
      + '<span style="opacity:.5;font-weight:400;font-size:13px;">  cycle ' + (order.cycle_id || "n/a") + '</span>'
      + '</div>'
      + '</div>';

    var justHtml = order.justification
      ? ('<div style="padding:12px 18px;background:#0a1225;border-bottom:1px solid #232c47;">'
         + '<div style="font-size:11px;opacity:.6;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">Justification structuree</div>'
         + '<div style="font-family:monospace;font-size:12px;line-height:1.5;">'
         + String(order.justification).replace(/</g,"&lt;").replace(/>/g,"&gt;")
         + '</div></div>')
      : '';

    var bodyId = "orderMemoBody_" + oid;
    var loadingHtml = '<div id="' + bodyId + '" style="padding:20px 18px;min-height:120px;">'
      + '<div style="opacity:.6;font-size:12px;">Generation du memo IA en cours...</div>'
      + '</div>';

    m.innerHTML = ''
      + '<div style="background:#141b32;border:1px solid #232c47;border-radius:10px;'
      +   'max-width:720px;width:92%;max-height:82vh;overflow:auto;position:relative;">'
      + '<button onclick="closeModal()" '
      +   'style="position:absolute;top:8px;right:12px;background:none;border:0;color:#8892b8;'
      +   'font-size:20px;cursor:pointer;line-height:1;">&times;</button>'
      + headerHtml
      + justHtml
      + loadingHtml
      + '</div>';
    m.style.display = "flex";

    /* Cache local par order_id */
    if (_orderMemoCache[oid]) {
      _renderOrderMemo(bodyId, _orderMemoCache[oid]);
      return;
    }

    try {
      var data = await _paFetch("/api/orders/" + oid + "/memo", {method: "POST"});
      _orderMemoCache[oid] = data;
      _renderOrderMemo(bodyId, data);
    } catch (err) {
      var el = document.getElementById(bodyId);
      if (el) {
        el.innerHTML = '<div style="color:#ff6b6b;font-size:12px;padding:10px 0;">'
          + 'Erreur generation memo : ' + (err && err.message ? err.message : String(err))
          + '</div>';
      }
    }
  }

  function _renderOrderMemo(bodyId, data) {
    var el = document.getElementById(bodyId);
    if (!el) return;

    if (data && data.error === "no_justification_available") {
      el.innerHTML = '<div style="padding:20px 0;opacity:.6;font-size:12.5px;text-align:center;">'
        + 'Cet ordre n\\u0027a pas de justification structuree.<br>'
        + '<span style="font-size:11px;opacity:.6;">(ordre anterieur au deploiement du Jalon 10)</span>'
        + '</div>';
      return;
    }

    var memo = data && data.memo ? String(data.memo) : "(memo vide)";
    var cachedTag = (data && data.cached)
      ? '<span style="opacity:.5;font-size:10.5px;margin-left:8px;">(cache)</span>'
      : '';
    var genTag = (data && data.generated_at)
      ? '<span style="opacity:.5;font-size:10.5px;">' + data.generated_at + '</span>'
      : '';

    el.innerHTML = ''
      + '<div style="display:flex;justify-content:space-between;align-items:center;'
      +   'margin-bottom:10px;font-size:11px;text-transform:uppercase;letter-spacing:.5px;opacity:.7;">'
      + '<span>Memo IA' + cachedTag + '</span>' + genTag
      + '</div>'
      + '<div style="white-space:pre-wrap;font-size:13px;line-height:1.55;">'
      + memo.replace(/</g,"&lt;").replace(/>/g,"&gt;")
      + '</div>';
  }
  /* [JUSTIFICATION_UI_V1] END openOrderMemoModal */

'''


def main():
    if not os.path.exists(F):
        print("[ERR] file not found:", F)
        return 2

    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    if MARK_BEGIN in src:
        print("[SKIP] UI patch already applied (marker present)")
        return 0

    # Verifie que les 2 blocs anciens existent verbatim
    if OLD_TEMPLATE not in src:
        print("[ERR] OLD_TEMPLATE not found verbatim")
        # dump pour debug
        print("[DEBUG] recherche 'list.innerHTML = orders.map' :")
        for m in re.finditer(r"list\.innerHTML\s*=\s*orders\.map", src):
            ln = src[:m.start()].count("\n") + 1
            print(f"  L{ln}: hit")
        return 3

    if OLD_LISTENERS not in src:
        print("[ERR] OLD_LISTENERS not found verbatim")
        return 4

    # Ancre pour la nouvelle fonction : "window.renderPendingApprovals = renderPendingApprovals;"
    anchor = "window.renderPendingApprovals = renderPendingApprovals;"
    if anchor not in src:
        print("[ERR] anchor for openOrderMemoModal not found")
        return 5

    print("[OK] all anchors found")

    new_src = src
    new_src = new_src.replace(OLD_TEMPLATE, NEW_TEMPLATE, 1)
    new_src = new_src.replace(OLD_LISTENERS, NEW_LISTENERS, 1)
    # Insere la fonction memo modal juste avant "window.renderPendingApprovals = ..."
    new_src = new_src.replace(anchor, MEMO_MODAL_FUNC.rstrip() + "\n\n  " + anchor, 1)

    if new_src == src:
        print("[ERR] no change produced")
        return 6

    # Backup + write
    bak = F + ".bak." + TS
    shutil.copy2(F, bak)
    print("[BAK]", bak)

    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print("[OK] written:", F)

    # Sanity checks
    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        check = fh.read()

    checks = [
        ("[JUSTIFICATION_UI_V1] BEGIN", "marker BEGIN template"),
        ("[JUSTIFICATION_UI_V1] END", "marker END template"),
        ("pa-memo-btn", "bouton Memo classe"),
        ("openOrderMemoModal", "fonction modal definie"),
        ("_orderMemoCache", "cache local"),
        ("/api/orders/", "fetch endpoint"),
    ]
    print()
    print("[POST-WRITE CHECKS]")
    for needle, label in checks:
        n = check.count(needle)
        tag = "OK" if n > 0 else "MISSING"
        print(f"  [{tag}] {label}: {n} occurrences")

    print()
    print("[NEXT] Ctrl+F5 dans le navigateur pour recharger app.js (cache-bust deja gere par ?v=...)")
    print("[NEXT] Puis Patch 5b : Memo IC PDF (memo_generator.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
