# -*- coding: utf-8 -*-
# Diag : check_freshness compare a today() vs day_t -> stale fail en replay
import os, sys, sqlite3
PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
WS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
for d in (PROD_DIR, WS_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)

TARGET = os.path.join(PROD_DIR, "market_regime_v1.py")
with open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()
lines = src.split("\n")

print("=" * 70)
print("[A] Recherche _check_freshness")
print("=" * 70)
import re
for m in re.finditer(r"def\s+(_?check_freshness\w*)\s*\(([^)]*)\):", src):
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: def {m.group(1)}({m.group(2)})")

# Affiche la fonction complete
m = re.search(r"^def\s+_check_freshness\s*\(", src, re.MULTILINE)
if m:
    line_no = src[:m.start()].count("\n")
    end = src.find("\n\ndef ", m.end())
    if end == -1:
        end = src.find("\n\n\n", m.end())
    body = src[m.start():end if end > 0 else m.start() + 1500]
    print(f"\n  Body (L{line_no+1}+):")
    for i, ln in enumerate(body.split("\n")[:30], start=line_no+1):
        print(f"    L{i:4d}: {ln}")

print("\n" + "=" * 70)
print("[B] Recherche _fetch_recent_closes")
print("=" * 70)
m = re.search(r"^def\s+_fetch_recent_closes\s*\(", src, re.MULTILINE)
if m:
    line_no = src[:m.start()].count("\n")
    end = src.find("\n\ndef ", m.end())
    body = src[m.start():end if end > 0 else m.start() + 1500]
    print(f"  Body (L{line_no+1}+):")
    for i, ln in enumerate(body.split("\n")[:30], start=line_no+1):
        print(f"    L{i:4d}: {ln}")

print("\n" + "=" * 70)
print("[C] EQUITY_BENCHMARK + CRYPTO_BENCHMARK + constantes freshness")
print("=" * 70)
for m in re.finditer(r"^(EQUITY_BENCHMARK|CRYPTO_BENCHMARK|FRESHNESS\w*|STALE\w*|MAX_AGE\w*)\s*=\s*(.+)$", src, re.MULTILINE):
    line_no = src[:m.start()].count("\n") + 1
    print(f"  L{line_no}: {m.group(0)}")

print("\n" + "=" * 70)
print("[D] Test runtime : detect_market_regime sur conn replay avec patch")
print("=" * 70)
from replay_db_view import open_replay_conn_at, monkey_patch_fred_vix, restore_fred_vix
import market_regime_v1

day_t = "2025-06-10"
conn = open_replay_conn_at(day_t, DB_PATH)
cur = conn.cursor()
cur.execute("SELECT MAX(date) FROM prices")
print(f"  max(date) prices replay : {cur.fetchone()[0]}")

# Verifie le ticker EQUITY_BENCHMARK
eq_bm = getattr(market_regime_v1, "EQUITY_BENCHMARK", "?")
cr_bm = getattr(market_regime_v1, "CRYPTO_BENCHMARK", "?")
print(f"  EQUITY_BENCHMARK = {eq_bm!r}")
print(f"  CRYPTO_BENCHMARK = {cr_bm!r}")

# Verifie le ticker dans instruments
cur.execute("SELECT id, ticker FROM instruments WHERE ticker=?", (eq_bm,))
row = cur.fetchone()
print(f"  instruments[{eq_bm}] = {dict(row) if row else None}")

# Verifie qu'on a bien des closes recents pour SPY
if row:
    cur.execute("SELECT MAX(date), COUNT(*) FROM prices WHERE instrument_id=?", (row["id"],))
    r2 = cur.fetchone()
    print(f"  prices[{eq_bm}]: max_date={r2[0]}  count={r2[1]}")

# Appelle _fetch_recent_closes direct
try:
    closes = market_regime_v1._fetch_recent_closes(conn, eq_bm, 35)
    print(f"  _fetch_recent_closes(conn, {eq_bm!r}, 35) -> {len(closes) if closes else 0} entries")
    if closes:
        # Premiere et derniere date
        first = closes[0] if isinstance(closes, list) else None
        last = closes[-1] if isinstance(closes, list) else None
        print(f"    first: {first}")
        print(f"    last : {last}")
except Exception as e:
    print(f"  EXCEPTION _fetch_recent_closes: {type(e).__name__}: {e}")

# Appelle _check_freshness
try:
    closes = market_regime_v1._fetch_recent_closes(conn, eq_bm, 35)
    fresh = market_regime_v1._check_freshness(closes)
    print(f"  _check_freshness(closes) -> {fresh}")
except Exception as e:
    print(f"  EXCEPTION _check_freshness: {type(e).__name__}: {e}")

# Appelle detect_market_regime avec patch
orig = monkey_patch_fred_vix(day_t, DB_PATH)
try:
    regime = market_regime_v1.detect_market_regime(conn)
    print(f"\n  detect_market_regime() retourne :")
    import json
    print(json.dumps(regime, indent=2, default=str)[:1500])
finally:
    restore_fred_vix(orig)
conn.close()
