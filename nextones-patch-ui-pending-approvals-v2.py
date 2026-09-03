# -*- coding: utf-8 -*-
# [PATCH_UI_PENDING_APPROVALS_V2]
# Patch UI cible sur les chemins reels (locator V1) :
#   - C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html
#   - C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js
# Idempotent (marker en commentaire). ASCII pur, Windows-safe.

import io
import os
import re
import sys
import time
import shutil

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
JS = os.path.join(ROOT, "app.js")

MARKER_JS = "/* [PATCH_UI_PENDING_APPROVALS_V2] */"
MARKER_HTML = "<!-- [PATCH_UI_PENDING_APPROVALS_V2] -->"


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    for p in (HTML, JS):
        if not os.path.exists(p):
            print("MISSING:", p); sys.exit(2)
    print("[HTML]", HTML)
    print("[JS]  ", JS)

    ts = time.strftime("%Y%m%d_%H%M%S")

    # --- HTML : injection de la card ---
    html_src = read_text(HTML)
    if MARKER_HTML in html_src:
        print("[SKIP] HTML marker already present")
    else:
        bak = HTML + ".bak." + ts
        shutil.copy2(HTML, bak)
        print("[BACKUP HTML]", bak)

        card_html = (
            '\n' + MARKER_HTML + '\n'
            '<section id="pending-approvals-card" '
            'style="margin:16px 0;padding:14px 16px;border:1px solid #2e3650;'
            'border-radius:10px;background:#1a2238;color:#e6e9ef;">\n'
            '  <div style="display:flex;align-items:center;justify-content:space-between;'
            'margin-bottom:10px;">\n'
            '    <h3 style="margin:0;font-size:15px;letter-spacing:.3px;">Pending Approvals '
            '<span id="pa-count" style="color:#ffb946;">(0)</span></h3>\n'
            '    <button id="pa-refresh-btn" style="background:#2c3e64;color:#e6e9ef;'
            'border:0;border-radius:6px;padding:6px 10px;cursor:pointer;">Refresh</button>\n'
            '  </div>\n'
            '  <div id="pa-list" style="display:flex;flex-direction:column;gap:6px;'
            'max-height:380px;overflow:auto;">\n'
            '    <div style="opacity:.6;font-size:12px;">Loading...</div>\n'
            '  </div>\n'
            '</section>\n'
        )

        # Strategies d'insertion par priorite :
        # 1) Juste apres un <main ...>
        # 2) Juste apres <body ...> ou apres un container connu (#dashboard, #app, etc.)
        # 3) Juste avant </body>
        inserted = False

        m_main = re.search(r"<main[^>]*>", html_src, re.IGNORECASE)
        if m_main:
            idx = m_main.end()
            html_src = html_src[:idx] + "\n" + card_html + html_src[idx:]
            inserted = True
            print("[OK] HTML card inseree apres <main>")

        if not inserted:
            m_body = re.search(r"<body[^>]*>", html_src, re.IGNORECASE)
            if m_body:
                idx = m_body.end()
                html_src = html_src[:idx] + "\n" + card_html + html_src[idx:]
                inserted = True
                print("[OK] HTML card inseree apres <body>")

        if not inserted:
            idx = html_src.lower().rfind("</body>")
            if idx >= 0:
                html_src = html_src[:idx] + card_html + "\n" + html_src[idx:]
                inserted = True
                print("[OK] HTML card inseree avant </body>")

        if not inserted:
            html_src = html_src.rstrip() + "\n" + card_html + "\n"
            print("[WARN] HTML card appended at EOF")

        write_text(HTML, html_src)
        print("[OK] HTML write")

    # --- JS : fonctions + polling ---
    js_src = read_text(JS)
    if MARKER_JS in js_src:
        print("[SKIP] JS marker already present")
        print("[DONE]", MARKER_JS)
        return

    bak_js = JS + ".bak." + ts
    shutil.copy2(JS, bak_js)
    print("[BACKUP JS]", bak_js)

    js_block = '''

''' + MARKER_JS + '''
// Pending Approvals card : fetch /api/orders/pending_approval + buttons Execute/Reject
(function(){
  function _fmtPrice(p) {
    if (p === null || p === undefined || isNaN(p)) return "-";
    return "$" + Number(p).toFixed(2);
  }
  function _fmtQty(q) {
    if (q === null || q === undefined || isNaN(q)) return "-";
    return Number(q).toLocaleString(undefined, {maximumFractionDigits: 4});
  }
  function _sideColor(s) {
    return (s === "buy") ? "#3ddc84" : "#ff6b6b";
  }

  async function _paFetch(url, opts) {
    // Prefer apiFetch si dispo (gere JWT), sinon fetch natif
    if (typeof apiFetch === "function") {
      try {
        const r = await apiFetch(url, opts || {});
        // apiFetch peut renvoyer Response ou objet
        if (r && typeof r.json === "function") return await r.json();
        return r;
      } catch (e) {
        console.warn("apiFetch failed, fallback fetch:", e);
      }
    }
    const r = await fetch(url, opts || {});
    return await r.json();
  }

  async function renderPendingApprovals() {
    const list = document.getElementById("pa-list");
    const cnt  = document.getElementById("pa-count");
    if (!list) return;

    try {
      const data = await _paFetch("/api/orders/pending_approval");
      const orders = (data && data.orders) ? data.orders : [];

      if (cnt) cnt.textContent = "(" + orders.length + ")";

      if (orders.length === 0) {
        list.innerHTML = '<div style="opacity:.55;font-size:12px;padding:6px 2px;">'
          + 'Aucun ordre en attente d\\u0027approval.</div>';
        return;
      }

      list.innerHTML = orders.map(function(o) {
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
      }).join("");

      list.querySelectorAll(".pa-exec-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          _paExecute(btn.getAttribute("data-id"));
        });
      });
      list.querySelectorAll(".pa-rej-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          _paReject(btn.getAttribute("data-id"));
        });
      });
    } catch (err) {
      console.error("renderPendingApprovals error:", err);
      list.innerHTML = '<div style="color:#ff6b6b;font-size:12px;">'
        + 'Erreur chargement : ' + (err && err.message ? err.message : err) + '</div>';
    }
  }

  async function _paExecute(orderId) {
    if (!confirm("Executer l\\u0027ordre #" + orderId + " ?")) return;
    try {
      const data = await _paFetch("/api/orders/" + orderId + "/execute", {method: "POST"});
      if (data && data.success) {
        alert("Ordre #" + orderId + " execute. Fill: " + _fmtPrice(data.fill_price)
              + " x " + _fmtQty(data.fill_quantity));
        renderPendingApprovals();
        if (typeof refreshDashboard === "function") refreshDashboard();
        if (typeof renderKPIs === "function") renderKPIs();
      } else {
        alert("Echec execute : " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Erreur execute : " + (err && err.message ? err.message : err));
    }
  }

  async function _paReject(orderId) {
    var reason = prompt("Raison du reject pour l\\u0027ordre #" + orderId + " ?", "user_rejected");
    if (reason === null) return;
    try {
      const data = await _paFetch("/api/orders/" + orderId + "/reject", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason: reason || "user_rejected"})
      });
      if (data && data.success) {
        renderPendingApprovals();
      } else {
        alert("Echec reject : " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Erreur reject : " + (err && err.message ? err.message : err));
    }
  }

  window.renderPendingApprovals = renderPendingApprovals;

  function _init() {
    var btn = document.getElementById("pa-refresh-btn");
    if (btn) btn.addEventListener("click", renderPendingApprovals);
    renderPendingApprovals();
    setInterval(renderPendingApprovals, 10000);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _init);
  } else {
    _init();
  }
})();
/* [/PATCH_UI_PENDING_APPROVALS_V2] */
'''

    js_src = js_src.rstrip() + "\n" + js_block + "\n"
    write_text(JS, js_src)
    print("[OK] JS write")
    print("[DONE]", MARKER_JS)


if __name__ == "__main__":
    main()
