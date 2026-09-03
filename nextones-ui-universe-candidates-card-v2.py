# -*- coding: utf-8 -*-
"""
[UI_UNIVERSE_V2]
Injecte la carte Universe Candidates dans le VRAI index.html
(racine du projet, pas static/).

Idempotent (marker HTML [UI_UNIVERSE_V2_BEGIN]/_END).
Backup auto.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-ui-universe-candidates-card-v2.py
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = ROOT / "index.html"

MARK_BEGIN = "<!-- [UI_UNIVERSE_V2_BEGIN] -->"
MARK_END   = "<!-- [UI_UNIVERSE_V2_END] -->"


CARD_HTML = """
""" + MARK_BEGIN + """
<section id="card-universe-candidates" class="card" style="margin-top: 16px;">
  <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
    <h3 style="margin:0;">Univers — Candidats</h3>
    <div>
      <button id="btn-univ-refresh" type="button">Rafraichir</button>
      <button id="btn-univ-scan" type="button">Lancer scan</button>
    </div>
  </div>
  <div id="univ-status" style="font-size:12px;opacity:0.7;padding:4px 0;"></div>
  <div style="overflow-x:auto;">
    <table id="univ-table" style="width:100%;border-collapse:collapse;">
      <thead>
        <tr>
          <th style="text-align:left;padding:6px;">Ticker</th>
          <th style="text-align:left;padding:6px;">Classe</th>
          <th style="text-align:right;padding:6px;">Score</th>
          <th style="text-align:right;padding:6px;">Cap %</th>
          <th style="text-align:right;padding:6px;">Mom 12-1</th>
          <th style="text-align:right;padding:6px;">Sharpe 90j</th>
          <th style="text-align:right;padding:6px;">Corr max</th>
          <th style="text-align:center;padding:6px;">Actions</th>
        </tr>
      </thead>
      <tbody id="univ-tbody">
        <tr><td colspan="8" style="padding:8px;opacity:0.7;">Chargement...</td></tr>
      </tbody>
    </table>
  </div>
</section>
<script>
(function(){
  if (window.__univ_v2_loaded) return;
  window.__univ_v2_loaded = true;

  function getToken(){
    return localStorage.getItem("token") || localStorage.getItem("access_token") || "";
  }
  function fmt(v, n){
    if (v === null || v === undefined || isNaN(parseFloat(v))) return "—";
    return parseFloat(v).toFixed(n);
  }
  function scorePill(s){
    if (s === null || s === undefined) return '<span style="opacity:0.5">—</span>';
    const v = parseFloat(s);
    let bg = '#888';
    if (v >= 0.8) bg = '#16a34a';
    else if (v >= 0.5) bg = '#eab308';
    else bg = '#dc2626';
    return `<span style="padding:2px 8px;border-radius:10px;color:#fff;background:${bg};font-size:11px;">${v.toFixed(2)}</span>`;
  }

  async function api(path, opts){
    opts = opts || {};
    opts.headers = Object.assign({"Content-Type":"application/json","Authorization":"Bearer "+getToken()}, opts.headers||{});
    const r = await fetch(path, opts);
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  }

  async function loadCandidates(){
    const tbody = document.getElementById("univ-tbody");
    const status = document.getElementById("univ-status");
    tbody.innerHTML = '<tr><td colspan="8" style="padding:8px;opacity:0.7;">Chargement...</td></tr>';
    try {
      const data = await api("/api/universe/candidates?status=pending&limit=50");
      const rows = data.candidates || [];
      if (!rows.length){
        tbody.innerHTML = '<tr><td colspan="8" style="padding:8px;opacity:0.7;">Aucun candidat en attente. Lance un scan.</td></tr>';
        status.textContent = "0 candidat pending";
        return;
      }
      tbody.innerHTML = rows.map(c => `
        <tr style="border-top:1px solid rgba(255,255,255,0.08);">
          <td style="padding:6px;font-weight:600;">${c.ticker || ""}</td>
          <td style="padding:6px;">${c.asset_class || ""}</td>
          <td style="padding:6px;text-align:right;">${scorePill(c.score)}</td>
          <td style="padding:6px;text-align:right;">${fmt(c.suggested_cap_pct, 1)}</td>
          <td style="padding:6px;text-align:right;">${fmt(c.momentum_12m_minus_1m, 3)}</td>
          <td style="padding:6px;text-align:right;">${fmt(c.sharpe_90d, 2)}</td>
          <td style="padding:6px;text-align:right;">${fmt(c.max_correl_existing, 2)}</td>
          <td style="padding:6px;text-align:center;white-space:nowrap;">
            <button data-act="approve" data-id="${c.id}" style="margin-right:4px;">Approuver</button>
            <button data-act="reject"  data-id="${c.id}" style="margin-right:4px;">Rejeter</button>
            <button data-act="info"    data-id="${c.id}">Rationale</button>
          </td>
        </tr>
      `).join("");
      status.textContent = `${rows.length} candidat(s) pending`;
    } catch(e){
      tbody.innerHTML = `<tr><td colspan="8" style="padding:8px;color:#dc2626;">Erreur: ${e.message}</td></tr>`;
    }
  }

  async function runScan(){
    const status = document.getElementById("univ-status");
    status.textContent = "Scan en cours...";
    try {
      const r = await api("/api/universe/scan", {method:"POST", body: JSON.stringify({top:5, dry_run:false})});
      status.textContent = "Scan termine: " + JSON.stringify(r.result || r).slice(0, 200);
      await loadCandidates();
    } catch(e){
      status.textContent = "Scan erreur: " + e.message;
    }
  }

  document.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t) return;
    if (t.id === "btn-univ-refresh"){ await loadCandidates(); return; }
    if (t.id === "btn-univ-scan"){ await runScan(); return; }
    if (t.dataset && t.dataset.act === "approve"){
      const id = t.dataset.id;
      if (!confirm(`Approuver le candidat #${id} ?`)) return;
      try {
        await api(`/api/universe/candidates/${id}/approve`, {method:"POST", body:"{}"});
        await loadCandidates();
      } catch(e){ alert("Erreur approve: "+e.message); }
    }
    if (t.dataset && t.dataset.act === "reject"){
      const id = t.dataset.id;
      const notes = prompt("Motif du rejet ?", "");
      if (notes === null) return;
      try {
        await api(`/api/universe/candidates/${id}/reject`, {method:"POST", body: JSON.stringify({notes})});
        await loadCandidates();
      } catch(e){ alert("Erreur reject: "+e.message); }
    }
    if (t.dataset && t.dataset.act === "info"){
      const id = t.dataset.id;
      try {
        const c = await api(`/api/universe/candidates/${id}`);
        alert(`${c.ticker}\\n\\nRationale:\\n${c.rationale || "(vide)"}\\n\\nSource: ${c.rationale_source || "?"}`);
      } catch(e){ alert("Erreur: "+e.message); }
    }
  });

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", loadCandidates);
  } else {
    loadCandidates();
  }
})();
</script>
""" + MARK_END + "\n"


def main() -> int:
    if not HTML.exists():
        print(f"[FAIL] {HTML} introuvable.")
        return 1
    print(f"[INFO] Cible: {HTML}")

    txt = HTML.read_text(encoding="utf-8-sig", errors="replace")

    if MARK_BEGIN in txt:
        start = txt.index(MARK_BEGIN)
        if MARK_END in txt[start:]:
            end_idx = txt.index(MARK_END, start) + len(MARK_END)
            txt = txt[:start] + CARD_HTML.strip() + txt[end_idx:]
            print("[INFO] bloc existant remplace.")
        else:
            txt = txt.rstrip() + "\n" + CARD_HTML
    else:
        # Inserer avant </body>
        if "</body>" in txt:
            txt = txt.replace("</body>", CARD_HTML + "</body>", 1)
            print("[INFO] insere avant </body>.")
        else:
            txt = txt.rstrip() + "\n" + CARD_HTML
            print("[WARN] </body> introuvable, append a la fin.")

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(f".html.bak-{ts}-jalon4-ui-v2")
    shutil.copy2(HTML, bak)
    print(f"[BACKUP] {bak.name}")

    HTML.write_text(txt, encoding="utf-8")
    print(f"[OK] {HTML.name} patche.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
