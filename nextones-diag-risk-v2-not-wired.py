#!/usr/bin/env python3
# nextones-diag-risk-v2-not-wired.py
# Confirme que Risk Engine v2 n'est PAS appele dans le pipeline du cycle
# 1. Verifie que les 10 ordres existent et leur risk_check_result
# 2. Confirme l'absence d'entree risk_pretrade_log pour le 29/05
# 3. Cherche l'invocation de check_pretrade dans le code (execution_engine, run_decision_cycle, etc.)

import sqlite3, re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("DIAG : Risk Engine v2 wired runtime ?")
print("=" * 78)

# === 1. Les 10 ordres du 29/05 ===
print("\n[1] Ordres entre 4895 et 4907 + risk_check_result")
print("-" * 78)
cur.execute("""
    SELECT id, instrument_id, side, quantity, status, risk_check_result, thesis_id, created_at
    FROM orders
    WHERE id BETWEEN 4895 AND 4907
    ORDER BY id
""")
rows = cur.fetchall()
print(f"  {'ID':<6} {'INST':<6} {'SIDE':<6} {'QTY':<10} {'STATUS':<12} {'RISK':<8} {'THESIS':<8} CREATED")
for r in rows:
    print(f"  {r['id']:<6} {str(r['instrument_id']):<6} {r['side']:<6} {str(r['quantity']):<10} {r['status']:<12} {str(r['risk_check_result']):<8} {str(r['thesis_id']):<8} {r['created_at']}")
print(f"\n  Total: {len(rows)} ordres")

# === 2. risk_pretrade_log : entrees du 29/05 ? ===
print("\n[2] risk_pretrade_log : entrees du 29/05 ?")
print("-" * 78)
cur.execute("""
    SELECT id, ts, symbol, side, qty, passed, blocked_by, marker
    FROM risk_pretrade_log
    WHERE ts LIKE '2026-05-29%'
    ORDER BY ts DESC
""")
today = cur.fetchall()
if not today:
    print("  AUCUNE entree pour le 29/05 — Risk v2 NON CALLED sur ce cycle")
else:
    for r in today:
        print(f"  {dict(r)}")

print(f"\n  Total entrees risk_pretrade_log toutes dates: ", end="")
cur.execute("SELECT COUNT(*) AS n FROM risk_pretrade_log")
print(cur.fetchone()['n'])

# === 3. Table instruments pour resoudre instrument_id -> ticker ===
print("\n[3] Resolution instrument_id -> ticker pour les 10 ordres")
print("-" * 78)
inst_ids = [r['instrument_id'] for r in rows]
if inst_ids:
    placeholders = ",".join("?" * len(set(inst_ids)))
    try:
        cur.execute(f"PRAGMA table_info(instruments)")
        ic = [c[1] for c in cur.fetchall()]
        tick_col = "ticker" if "ticker" in ic else ("symbol" if "symbol" in ic else None)
        if tick_col:
            cur.execute(f"SELECT id, {tick_col} FROM instruments WHERE id IN ({placeholders})", list(set(inst_ids)))
            mapping = {r['id']: r[tick_col] for r in cur.fetchall()}
            for r in rows:
                print(f"  #{r['id']} instrument_id={r['instrument_id']} -> {mapping.get(r['instrument_id'], '?')}")
    except Exception as e:
        print(f"  err: {e}")

# === 4. Cherche check_pretrade / risk_v2 dans le code Python ===
print("\n[4] Invocations check_pretrade / risk_pretrade dans le code")
print("-" * 78)
patterns = [
    r"check_pretrade",
    r"risk_pretrade",
    r"risk_v2",
    r"RISK_V2",
    r"pretrade_check",
    r"from risk_pretrade",
    r"import risk_pretrade",
]
for py in ROOT.glob("*.py"):
    try:
        content = py.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    for pat in patterns:
        for m in re.finditer(pat, content, re.IGNORECASE):
            # ligne du match
            start = content.rfind("\n", 0, m.start()) + 1
            end = content.find("\n", m.end())
            line = content[start:end].rstrip()
            ln = content[:m.start()].count("\n") + 1
            print(f"  {py.name}:L{ln}  {line[:120]}")

# === 5. Verifie marker [RISK_V2_WIRED_V1] dans execution_engine.py ===
print("\n[5] Marker [RISK_V2_WIRED] dans le code")
print("-" * 78)
for py in ROOT.glob("*.py"):
    try:
        content = py.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    for marker in ["[RISK_V2_WIRED", "[RISK_V2]", "RISK_V2_WIRED_V1"]:
        if marker in content:
            idx = content.find(marker)
            ln = content[:idx].count("\n") + 1
            print(f"  {py.name}:L{ln} contient {marker}")

conn.close()
print("\n" + "=" * 78)
