# -*- coding: utf-8 -*-
# Diag v2 : contexte autour des vix_value=None + test isole du monkey-patch
import os
import sys
import sqlite3

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
WS_DIR = os.path.dirname(os.path.abspath(__file__))

for d in (PROD_DIR, WS_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

TARGET = os.path.join(PROD_DIR, "market_regime_v1.py")

with open(TARGET, "r", encoding="utf-8-sig") as f:
    lines = f.read().split("\n")

print("=" * 70)
print("[A] Contexte autour de L322 (vix = _fetch_vix_from_fred):")
print("=" * 70)
for ln in range(max(0, 322 - 15), min(len(lines), 322 + 10)):
    marker = " >>" if (ln + 1) == 322 else "   "
    print(f"{marker} L{ln+1:4d}: {lines[ln]}")

print()
print("=" * 70)
print("[B] Contexte autour de L356 (vix_value = None):")
print("=" * 70)
for ln in range(max(0, 356 - 12), min(len(lines), 356 + 5)):
    marker = " >>" if (ln + 1) == 356 else "   "
    print(f"{marker} L{ln+1:4d}: {lines[ln]}")

print()
print("=" * 70)
print("[C] Contexte autour de L377 (vix_value = None):")
print("=" * 70)
for ln in range(max(0, 377 - 12), min(len(lines), 377 + 5)):
    marker = " >>" if (ln + 1) == 377 else "   "
    print(f"{marker} L{ln+1:4d}: {lines[ln]}")

print()
print("=" * 70)
print("[D] Test isole du monkey-patch")
print("=" * 70)

from replay_db_view import monkey_patch_fred_vix, restore_fred_vix
import market_regime_v1

# Sauve original
orig = market_regime_v1._fetch_vix_from_fred
print(f"  Original  : {orig}")

# Test direct lecture macro_history pour VIX a 2025-06-10
day_t = "2025-06-10"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    "SELECT date, value FROM macro_history WHERE series_code='VIX' AND date <= ? ORDER BY date DESC LIMIT 3",
    (day_t,),
)
rows = cur.fetchall()
print(f"  macro_history VIX <= {day_t} (top 3):")
for r in rows:
    print(f"    date={r[0]}  value={r[1]}")
conn.close()

# Applique le monkey-patch
patched_orig = monkey_patch_fred_vix(day_t, DB_PATH)
print(f"  After patch: {market_regime_v1._fetch_vix_from_fred}")
print(f"  Patch is new func: {market_regime_v1._fetch_vix_from_fred is not orig}")

# Appelle la fonction patchee
try:
    val = market_regime_v1._fetch_vix_from_fred()
    print(f"  _fetch_vix_from_fred() retourne : {val!r}  (type {type(val).__name__})")
except Exception as e:
    print(f"  EXCEPTION : {type(e).__name__}: {e}")

# Appelle aussi via le namespace local de detect_market_regime
# (test : est-ce que la fonction interne 'detect_market_regime' resout
#  _fetch_vix_from_fred via le module ou via une closure ?)
import inspect
src = inspect.getsource(market_regime_v1.detect_market_regime)
print(f"\n  detect_market_regime source ({len(src)} chars, premieres 30 lignes):")
for i, line in enumerate(src.split("\n")[:30], 1):
    print(f"    {i:3d}: {line}")

restore_fred_vix(patched_orig)
print(f"\n  After restore: {market_regime_v1._fetch_vix_from_fred is orig}")
