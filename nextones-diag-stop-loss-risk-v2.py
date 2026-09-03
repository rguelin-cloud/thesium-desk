# -*- coding: utf-8 -*-
# nextones-diag-stop-loss-risk-v2.py
# Diag : trouver le stop-loss -8% dans risk_pretrade.py
#   - Constante / seuil
#   - Logique de check (positions ouvertes vs prix actuel)
#   - Statut actuel (warning ou block ?)
#   - Format du dict de retour (pour patcher la transformation warning->block)
#
# Egalement : positions actuelles avec pnl_pct courant (pour anticiper les
# blocages legitimes).

import os
import sys
import sqlite3
import re

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RP = os.path.join(PROD, "risk_pretrade.py")
DB = os.path.join(PROD, "thesium.db")

print()
print("=" * 72)
print("DIAG : stop-loss -8% dans risk_pretrade.py")
print("=" * 72)

with open(RP, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

lines = content.split("\n")

# ----------------------------------------------------------------------
# [1] Cherche les constantes/seuils relatifs au stop-loss
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[1] Constantes/seuils stop-loss (regex 0.08, -8, STOP_LOSS, stop_loss)")
print("-" * 72)

patterns = [
    (r"STOP_LOSS", "STOP_LOSS"),
    (r"stop_loss", "stop_loss"),
    (r"-0\.08", "-0.08"),
    (r"0\.08", "0.08"),
    (r"-8\b", "-8"),
    (r"\bstop\b", "stop"),
]

found = {}
for i, ln in enumerate(lines):
    for pat, label in patterns:
        if re.search(pat, ln):
            found.setdefault(label, []).append((i + 1, ln.strip()))

for label, occs in found.items():
    print()
    print("  [%s] %d occurrences :" % (label, len(occs)))
    for ln_no, txt in occs[:10]:
        print("    L%d: %s" % (ln_no, txt[:170]))

# ----------------------------------------------------------------------
# [2] Toutes les fonctions def
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[2] Fonctions definies dans risk_pretrade.py")
print("-" * 72)

for i, ln in enumerate(lines):
    s = ln.strip()
    if s.startswith("def "):
        print("  L%d: %s" % (i + 1, s[:180]))

# ----------------------------------------------------------------------
# [3] Tous les markers existants dans le fichier
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[3] Markers deja presents dans risk_pretrade.py")
print("-" * 72)

for i, ln in enumerate(lines):
    if "[RISK_V2" in ln or "[BROKER_CHECK" in ln or "[CONVERGENCE" in ln or "[STOP_LOSS" in ln:
        print("  L%d: %s" % (i + 1, ln.strip()[:170]))

# ----------------------------------------------------------------------
# [4] Cle "warnings" ou "blocked_by" pour comprendre le format de retour
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[4] Lignes touchant 'warnings' / 'blocked_by' / 'passed'")
print("-" * 72)

for i, ln in enumerate(lines):
    if "warnings" in ln or "blocked_by" in ln or '"passed"' in ln or "'passed'" in ln:
        print("  L%d: %s" % (i + 1, ln.strip()[:170]))

# ----------------------------------------------------------------------
# [5] Positions actuelles + pnl_pct pour anticiper les blocages
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[5] Positions actuelles (qty > 0) avec PnL %")
print("-" * 72)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    """SELECT i.ticker,
              pp.quantity,
              pp.avg_cost,
              pp.current_price,
              pp.unrealized_pnl,
              pp.weight_pct
       FROM portfolio_positions pp
       JOIN instruments i ON i.id = pp.instrument_id
       WHERE pp.quantity > 0
       ORDER BY pp.weight_pct DESC"""
).fetchall()

print()
print("  %-8s %-8s %-10s %-10s %-10s %-8s" % (
    "ticker", "qty", "avg_cost", "price", "pnl_pct", "weight"))
print("  " + "-" * 60)
for r in rows:
    avg = r["avg_cost"] or 0.0
    price = r["current_price"] or 0.0
    pnl_pct = ((price - avg) / avg * 100) if avg else 0.0
    flag = " <-- STOP-LOSS" if pnl_pct <= -8.0 else ""
    print("  %-8s %-8s %-10.4f %-10.4f %+9.2f%% %-7.2f%s" % (
        r["ticker"], r["quantity"], avg, price, pnl_pct,
        r["weight_pct"] or 0.0, flag))

conn.close()

print()
print("=" * 72)
