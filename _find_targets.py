"""
_find_targets.py — Trouve où sont stockés les target_weights utilisés par le Reconciler.

Liste toutes les tables et cherche les colonnes 'target', 'weight', 'allocation'.
"""
import sqlite3
import os

DB_PATH = "thesium.db"

if not os.path.exists(DB_PATH):
    print(f"ERREUR : {DB_PATH} introuvable")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row


def section(t):
    print()
    print("=" * 80)
    print(t)
    print("=" * 80)


# ---------------------------------------------------------------------------
# 1. Liste toutes les tables
# ---------------------------------------------------------------------------
section("1. Toutes les tables de la DB")
tables = [r["name"] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
for t in tables:
    print(f"  - {t}")


# ---------------------------------------------------------------------------
# 2. Tables avec colonnes 'target' / 'weight' / 'allocation'
# ---------------------------------------------------------------------------
section("2. Tables contenant 'target' / 'weight' / 'allocation' / 'cible'")
keywords = ["target", "weight", "alloc", "cible"]
for t in tables:
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        matches = [c for c in cols if any(kw in c.lower() for kw in keywords)]
        if matches:
            print(f"  Table '{t}' : {matches}")
            print(f"    Toutes les colonnes : {cols}")
            # Count rows
            n = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"    Nombre de lignes : {n}")
    except Exception as e:
        print(f"  Erreur sur {t} : {e}")


# ---------------------------------------------------------------------------
# 3. Affiche le contenu des tables candidates
# ---------------------------------------------------------------------------
section("3. Contenu des tables candidates")
candidates = []
for t in tables:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
    if any(any(kw in c.lower() for kw in keywords) for c in cols):
        candidates.append(t)

for t in candidates:
    print()
    print(f"--- Table : {t} ---")
    try:
        rows = conn.execute(f"SELECT * FROM {t} LIMIT 20").fetchall()
        if not rows:
            print("  (vide)")
        else:
            cols = list(rows[0].keys())
            print(f"  Colonnes : {cols}")
            for r in rows:
                print(f"  {dict(r)}")
    except Exception as e:
        print(f"  Erreur : {e}")


# ---------------------------------------------------------------------------
# 4. portfolio_positions (peut-être que target est ici)
# ---------------------------------------------------------------------------
section("4. portfolio_positions (avec ticker, weight_pct, target_weight_pct ?)")
try:
    rows = conn.execute("""
        SELECT i.ticker, p.quantity, p.current_price, p.weight_pct,
               p.* 
        FROM portfolio_positions p
        JOIN instruments i ON i.id = p.instrument_id
        WHERE p.quantity > 0
    """).fetchall()
    if rows:
        cols = list(rows[0].keys())
        print(f"  Colonnes : {cols}")
        for r in rows:
            d = dict(r)
            print(f"  {d}")
except Exception as e:
    print(f"  Erreur : {e}")


# ---------------------------------------------------------------------------
# 5. Cherche aussi dans portfolio_state (souvent les targets globaux y sont)
# ---------------------------------------------------------------------------
section("5. portfolio_state (toutes colonnes)")
try:
    rows = conn.execute("SELECT * FROM portfolio_state").fetchall()
    if rows:
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if isinstance(v, str) and len(v) > 100:
                    v = v[:100] + "..."
                print(f"  {k}: {v}")
            print()
except Exception as e:
    print(f"  Erreur : {e}")


conn.close()
print()
print("Fin du diagnostic.")
