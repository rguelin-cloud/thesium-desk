# -*- coding: utf-8 -*-
"""
NEXTONES - Jalon 4 - UI carte 'Univers - Candidats'
Marker: [UI_UNIVERSE_V1]

Injecte la carte HTML+JS dans static/index.html:
  - Section visible avec Top 5 candidats pending
  - Boutons Approuver / Rejeter / Voir rationale
  - Bouton manuel 'Lancer scan'

Idempotent : detecte les markers et ne reinsere pas.
Backup automatique. ASCII-safe (texte HTML/JS sans accents prononces).

Usage:
    py -3.13 nextones-ui-universe-candidates-card.py
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

HTML_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\static\index.html")
MARKER_HTML_BEGIN = "<!-- [UI_UNIVERSE_V1] BEGIN -->"
MARKER_HTML_END = "<!-- [UI_UNIVERSE_V1] END -->"

ANCHOR_BEFORE = "</body>"  # On insere avant </body>

# Carte HTML+CSS+JS - ASCII only (utilise entites HTML &eacute; etc si besoin)
CARD_HTML = """
<!-- [UI_UNIVERSE_V1] BEGIN -->
<style>
  .univ-card {
    background: var(--surface, #1c1b19);
    border: 1px solid var(--border, #393836);
    border-radius: 8px;
    padding: 16px;
    margin: 16px 0;
    color: var(--text, #cdccca);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  .univ-card h3 {
    margin: 0 0 12px 0;
    color: var(--primary, #4f98a3);
    font-size: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .univ-card .univ-actions { display: flex; gap: 8px; }
  .univ-card button {
    background: var(--primary, #4f98a3);
    color: #fff;
    border: 0;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
  }
  .univ-card button.secondary { background: #555; }
  .univ-card button.danger { background: #a12c7b; }
  .univ-card button:disabled { opacity: 0.5; cursor: not-allowed; }
  .univ-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .univ-table th, .univ-table td {
    text-align: left;
    padding: 8px 6px;
    border-bottom: 1px solid var(--border, #393836);
  }
  .univ-table th { color: var(--text-muted, #797876); font-weight: 600; font-size: 11px; }
  .univ-table tr:hover td { background: rgba(79, 152, 163, 0.06); }
  .univ-score-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 600;
    font-size: 11px;
  }
  .univ-score-high { background: #437a22; color: #fff; }
  .univ-score-mid  { background: #964219; color: #fff; }
  .univ-score-low  { background: #5a5957; color: #fff; }
  .univ-empty { color: var(--text-muted, #797876); font-style: italic; padding: 12px 0; }
  .univ-rationale {
    background: rgba(79, 152, 163, 0.08);
    border-left: 2px solid var(--primary, #4f98a3);
    padding: 8px 12px;
    margin: 4px 0 0 0;
    font-size: 12px;
    color: var(--text, #cdccca);
    display: none;
  }
  .univ-rationale.open { display: block; }
</style>

<div id="univ-candidates-card" class="univ-card">
  <h3>
    <span>Univers - Candidats (Jalon 4)</span>
    <span class="univ-actions">
      <button id="univ-refresh-btn" class="secondary" type="button">Rafraichir</button>
      <button id="univ-scan-btn" type="button">Lancer scan</button>
    </span>
  </h3>
  <div id="univ-status" class="univ-empty">Chargement...</div>
  <table class="univ-table" id="univ-table" style="display:none;">
    <thead>
      <tr>
        <th>Ticker</th>
        <th>Classe</th>
        <th>Score</th>
        <th>Cap</th>
        <th>Mom 12-1</th>
        <th>Sharpe 90j</th>
        <th>Corr max</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody id="univ-tbody"></tbody>
  </table>
</div>

<script>
(function() {
  if (window.__univ_v1_loaded) return;
  window.__univ_v1_loaded = true;

  function authHeaders() {
    var t = localStorage.getItem("token") || localStorage.getItem("access_token") || "";
    return t ? { "Authorization": "Bearer " + t } : {};
  }

  function fmtPct(x, decimals) {
    if (x === null || x === undefined || isNaN(x)) return "-";
    return (x * 100).toFixed(decimals || 1) + "%";
  }

  function scorePill(score) {
    if (score === null || score === undefined) return '<span class="univ-score-pill univ-score-low">-</span>';
    var cls = score > 0.8 ? "univ-score-high" : (score >= 0.5 ? "univ-score-mid" : "univ-score-low");
    return '<span class="univ-score-pill ' + cls + '">' + score.toFixed(2) + "</span>";
  }

  function renderRow(c) {
    var corrTxt = (c.max_correl_existing === null || c.max_correl_existing === undefined)
      ? "-"
      : (c.max_correl_existing.toFixed(2) + (c.max_correl_with ? " (" + c.max_correl_with + ")" : ""));
    var capTxt = c.suggested_cap_pct ? (c.suggested_cap_pct * 100).toFixed(0) + "%" : "-";
    var html =
      '<tr data-id="' + c.id + '">' +
      '  <td><strong>' + c.ticker + '</strong><br><small>' + (c.name || "") + '</small></td>' +
      '  <td>' + (c.asset_class || "-") + '</td>' +
      '  <td>' + scorePill(c.score) + '</td>' +
      '  <td>' + capTxt + '</td>' +
      '  <td>' + fmtPct(c.momentum_12m_minus_1m, 1) + '</td>' +
      '  <td>' + (c.sharpe_90d !== null && c.sharpe_90d !== undefined ? c.sharpe_90d.toFixed(2) : "-") + '</td>' +
      '  <td>' + corrTxt + '</td>' +
      '  <td>' +
      '    <button type="button" class="univ-approve">Approuver</button> ' +
      '    <button type="button" class="univ-reject danger">Rejeter</button> ' +
      '    <button type="button" class="univ-view secondary">Rationale</button>' +
      '  </td>' +
      '</tr>' +
      '<tr class="univ-rationale-row" data-id="' + c.id + '" style="display:none;">' +
      '  <td colspan="8"><div class="univ-rationale">' + (c.rationale || "(aucune)") + '</div></td>' +
      '</tr>';
    return html;
  }

  async function loadCandidates() {
    var statusEl = document.getElementById("univ-status");
    var tableEl = document.getElementById("univ-table");
    statusEl.textContent = "Chargement...";
    statusEl.style.display = "block";
    tableEl.style.display = "none";
    try {
      var r = await fetch("/api/universe/candidates?status=pending&limit=20", {
        headers: authHeaders(),
      });
      if (!r.ok) throw new Error("HTTP " + r.status);
      var data = await r.json();
      var tbody = document.getElementById("univ-tbody");
      tbody.innerHTML = "";
      if (!data.candidates || data.candidates.length === 0) {
        statusEl.textContent = "Aucun candidat en attente. Lancer un scan pour en proposer.";
        return;
      }
      data.candidates.forEach(function(c) {
        tbody.insertAdjacentHTML("beforeend", renderRow(c));
      });
      statusEl.style.display = "none";
      tableEl.style.display = "table";
      bindRowEvents();
    } catch (e) {
      statusEl.textContent = "Erreur de chargement : " + e.message;
    }
  }

  function bindRowEvents() {
    document.querySelectorAll("#univ-tbody .univ-approve").forEach(function(btn) {
      btn.onclick = async function() {
        var row = btn.closest("tr");
        var id = row.getAttribute("data-id");
        if (!confirm("Approuver ce candidat ? Il sera ajoute a instruments + target_universe.")) return;
        btn.disabled = true;
        try {
          var r = await fetch("/api/universe/candidates/" + id + "/approve", {
            method: "POST",
            headers: Object.assign({"Content-Type": "application/json"}, authHeaders()),
            body: "{}",
          });
          var data = await r.json();
          if (!r.ok) throw new Error(JSON.stringify(data));
          alert("Approuve : " + (data.ticker || id));
          loadCandidates();
        } catch (e) {
          alert("Erreur : " + e.message);
          btn.disabled = false;
        }
      };
    });
    document.querySelectorAll("#univ-tbody .univ-reject").forEach(function(btn) {
      btn.onclick = async function() {
        var row = btn.closest("tr");
        var id = row.getAttribute("data-id");
        var notes = prompt("Motif de rejet (optionnel) :", "") || "";
        btn.disabled = true;
        try {
          var r = await fetch("/api/universe/candidates/" + id + "/reject", {
            method: "POST",
            headers: Object.assign({"Content-Type": "application/json"}, authHeaders()),
            body: JSON.stringify({notes: notes}),
          });
          if (!r.ok) throw new Error("HTTP " + r.status);
          loadCandidates();
        } catch (e) {
          alert("Erreur : " + e.message);
          btn.disabled = false;
        }
      };
    });
    document.querySelectorAll("#univ-tbody .univ-view").forEach(function(btn) {
      btn.onclick = function() {
        var row = btn.closest("tr");
        var id = row.getAttribute("data-id");
        var rat = document.querySelector('.univ-rationale-row[data-id="' + id + '"]');
        if (!rat) return;
        var div = rat.querySelector(".univ-rationale");
        if (rat.style.display === "none") {
          rat.style.display = "table-row";
          div.classList.add("open");
        } else {
          rat.style.display = "none";
          div.classList.remove("open");
        }
      };
    });
  }

  document.getElementById("univ-refresh-btn").onclick = loadCandidates;
  document.getElementById("univ-scan-btn").onclick = async function() {
    var btn = this;
    if (!confirm("Lancer un scan immediat ? (60-120 secondes)")) return;
    btn.disabled = true;
    btn.textContent = "Scan en cours...";
    try {
      var r = await fetch("/api/universe/scan", {
        method: "POST",
        headers: Object.assign({"Content-Type": "application/json"}, authHeaders()),
        body: JSON.stringify({top: 5}),
      });
      var data = await r.json();
      if (!r.ok) throw new Error(JSON.stringify(data));
      alert("Scan termine : " + data.inserted + " candidats inseres (" + (data.top_tickers || []).join(", ") + ")");
      loadCandidates();
    } catch (e) {
      alert("Erreur scan : " + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Lancer scan";
    }
  };

  // Auto-load au demarrage
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadCandidates);
  } else {
    loadCandidates();
  }
})();
</script>
<!-- [UI_UNIVERSE_V1] END -->
"""


def main():
    if not HTML_PATH.exists():
        print(f"ERROR: index.html introuvable - {HTML_PATH}")
        sys.exit(1)

    src = HTML_PATH.read_text(encoding="utf-8-sig")
    if MARKER_HTML_BEGIN in src:
        print("[SKIP] Marker [UI_UNIVERSE_V1] deja present.")
        return

    if ANCHOR_BEFORE not in src:
        print(f"[ERR] Ancre {ANCHOR_BEFORE} introuvable dans index.html")
        sys.exit(2)

    bak = HTML_PATH.with_suffix(
        HTML_PATH.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}-jalon4"
    )
    shutil.copy2(HTML_PATH, bak)
    print(f"[BACKUP] {bak}")

    new_src = src.replace(ANCHOR_BEFORE, CARD_HTML.strip() + "\n" + ANCHOR_BEFORE, 1)
    HTML_PATH.write_text(new_src, encoding="utf-8")

    n_begin = new_src.count(MARKER_HTML_BEGIN)
    n_end = new_src.count(MARKER_HTML_END)
    print(f"[OK] Patch applique. Markers BEGIN={n_begin} END={n_end}")
    if n_begin != 1 or n_end != 1:
        print("[ERR] Compte de markers inattendu.")
        sys.exit(3)
    print("[NEXT] F5 dans le navigateur (Ctrl+F5 pour cache hard).")


if __name__ == "__main__":
    main()
