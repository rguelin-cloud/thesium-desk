# -*- coding: utf-8 -*-
# [PATCH_UI_PENDING_APPROVALS_V1]
# Ajoute une card "Pending Approvals" dans le dashboard :
#  - HTML : nouveau bloc <div id="pending-approvals-card"> insere dans static/index.html
#  - JS   : fonction renderPendingApprovals() + polling 10s + handlers Execute/Reject
#           ajoutes a la fin de static/js/app.js (idempotent, marker en commentaire).
# ASCII pur, Windows-safe. Read utf-8-sig / write utf-8 sans BOM. Backup .bak.<ts>.

import io
import os
import re
import sys
import time
import shutil

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# On essaie plusieurs emplacements possibles pour les statics
CAND_HTML = [
    os.path.join(ROOT, "static", "index.html"),
    os.path.join(ROOT, "ui", "index.html"),
    os.path.join(ROOT, "frontend", "index.html"),
]
CAND_JS = [
    os.path.join(ROOT, "static", "js", "app.js"),
    os.path.join(ROOT, "static", "app.js"),
    os.path.join(ROOT, "ui", "js", "app.js"),
    os.path.join(ROOT, "frontend", "js", "app.js"),
]

MARKER = "/* [PATCH_UI_PENDING_APPROVALS_V1] */"
MARKER_HTML = "<!-- [PATCH_UI_PENDING_APPROVALS_V1] -->"


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def find_first(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return None


def main():
    html_path = find_first(CAND_HTML)
    js_path = find_first(CAND_JS)

    if not html_path:
        print("[FAIL] index.html introuvable. Cands testees :")
        for c in CAND_HTML: print("  ", c)
        sys.exit(2)
    if not js_path:
        print("[FAIL] app.js introuvable. Cands testees :")
        for c in CAND_JS: print("  ", c)
        sys.exit(2)

    print("[HTML]", html_path)
    print("[JS]  ", js_path)

    ts = time.strftime("%Y%m%d_%H%M%S")

    # --- HTML : injection de la card ---
    html_src = read_text(html_path)
    if MARKER_HTML in html_src:
        print("[SKIP] HTML marker already present")
    else:
        bak = html_path + ".bak." + ts
        shutil.copy2(html_path, bak)
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

        # Strategie d'insertion : juste apres <main ...> ou juste avant </body>
        inserted = False
        m_main = re.search(r"<main[^>]*>", html_src, re.IGNORECASE)
        if m_main:
            idx = m_main.end()
            html_src = html_src[:idx] + "\n" + card_html + html_src[idx:]
            inserted = True
            print("[OK] HTML card inseree apres <main>")

        if not inserted:
            idx = html_src.lower().rfind("</body>")
            if idx >= 0:
                html_src = html_src[:idx] + card_html + "\n" + html_src[idx:]
                inserted = True
                print("[OK] HTML card inseree avant </body>")

        if not inserted:
            html_src = html_src.rstrip() + "\n" + card_html + "\n"
            print("[WARN] HTML card appended at EOF (pas de <main> ni </body>)")

        write_text(html_path, html_src)
        print("[OK] HTML write")

    # --- JS : fonctions + polling ---
    js_src = read_text(js_path)
    if MARKER in js_src:
        print("[SKIP] JS marker already present")
        print("[DONE]", MARKER)
        return

    bak_js = js_path + ".bak." + ts
    shutil.copy2(js_path, bak_js)
    print("[BACKUP JS]", bak_js)

    js_block = '''

''' + MARKER + '''
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

  async function renderPendingApprovals() {
    const list = document.getElementById("pa-list");
    const cnt  = document.getElementById("pa-count");
    if (!list) return;

    try {
      const fetchFn = (typeof apiFetch === "function") ? apiFetch : fetch;
      const resp = await fetchFn("/api/orders/pending_approval");
      const data = (resp.json) ? await resp.json() : resp;
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

      // Bind buttons
      list.querySelectorAll(".pa-exec-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          var id = btn.getAttribute("data-id");
          _paExecute(id);
        });
      });
      list.querySelectorAll(".pa-rej-btn").forEach(function(btn) {
        btn.addEventListener("click", function() {
          var id = btn.getAttribute("data-id");
          _paReject(id);
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
      const fetchFn = (typeof apiFetch === "function") ? apiFetch : fetch;
      const resp = await fetchFn("/api/orders/" + orderId + "/execute", {method: "POST"});
      const data = (resp.json) ? await resp.json() : resp;
      if (data && data.success) {
        alert("Ordre #" + orderId + " execute. Fill: " + _fmtPrice(data.fill_price)
              + " x " + _fmtQty(data.fill_quantity));
        renderPendingApprovals();
        if (typeof refreshDashboard === "function") refreshDashboard();
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
      const fetchFn = (typeof apiFetch === "function") ? apiFetch : fetch;
      const resp = await fetchFn("/api/orders/" + orderId + "/reject", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({reason: reason || "user_rejected"})
      });
      const data = (resp.json) ? await resp.json() : resp;
      if (data && data.success) {
        renderPendingApprovals();
      } else {
        alert("Echec reject : " + JSON.stringify(data));
      }
    } catch (err) {
      alert("Erreur reject : " + (err && err.message ? err.message : err));
    }
  }

  // Expose
  window.renderPendingApprovals = renderPendingApprovals;

  // Init + polling
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
/* [/PATCH_UI_PENDING_APPROVALS_V1] */
'''

    js_src = js_src.rstrip() + "\n" + js_block + "\n"
    write_text(js_path, js_src)
    print("[OK] JS write")
    print("[DONE]", MARKER)


if __name__ == "__main__":
    main()
