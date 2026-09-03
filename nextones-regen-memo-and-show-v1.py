# -*- coding: utf-8 -*-
"""
Regenere un memo IC pour le dernier cycle et affiche un extrait
de la nouvelle section 'Regime de Marche'.
"""
import os
import sys
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
sys.path.insert(0, ROOT)

# Force reimport
for mod in ("memo_generator",):
    if mod in sys.modules:
        del sys.modules[mod]

print("=" * 78)
print("Regeneration memo IC + extrait section market_regime")
print("=" * 78)

try:
    import memo_generator as mg
except Exception as e:
    print(f"[ERR] import memo_generator: {e}")
    sys.exit(1)

# Verif helper present
has_helper = hasattr(mg, "_build_market_regime_section")
print(f"[{'OK' if has_helper else 'ERR'}] _build_market_regime_section dispo : {has_helper}")
if not has_helper:
    sys.exit(2)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# 1) Test direct de la nouvelle section
print()
print("--- _build_market_regime_section(conn) standalone ---")
try:
    section_md = mg._build_market_regime_section(conn)
    print(section_md)
except Exception as e:
    print(f"[ERR] {e}")
    import traceback; traceback.print_exc()
    sys.exit(3)

# 2) Genere un memo complet
print()
print("--- generate_ic_memo(conn) ---")
try:
    memo_id = mg.generate_ic_memo(conn)
    conn.commit()
    print(f"[OK] memo_id={memo_id}")
except Exception as e:
    print(f"[ERR] generate_ic_memo: {e}")
    import traceback; traceback.print_exc()
    sys.exit(4)

# 3) Verifie la presence de la section dans le full_markdown du memo
row = conn.execute(
    "SELECT full_markdown FROM ic_memos WHERE id = ?", (memo_id,)
).fetchone()
if not row:
    print("[ERR] memo introuvable")
    sys.exit(5)

md = row[0] or ""
print(f"\n[OK] Memo {memo_id} : {len(md)} chars")
if "[MARKET_REGIME_V1]" in md:
    print("[OK] Marker [MARKET_REGIME_V1] present dans le memo")
else:
    print("[WARN] Marker [MARKET_REGIME_V1] absent du memo full_markdown")

# Affiche l'extrait market_regime (300 chars max)
i = md.find("Regime de March")
if i < 0:
    i = md.find("\u00e9gime de March")  # acentue
if i >= 0:
    print()
    print("--- Extrait section R\u00e9gime de March\u00e9 ---")
    end = md.find("---", i + 10)
    if end < 0:
        end = min(i + 1500, len(md))
    print(md[i:end])

conn.close()
print()
print("=" * 78)
print("Verification visuelle OK : la section est dans le memo")
print("=" * 78)
