# [DIAG_CYCLE_STRUCTURE_V2] Recherche elargie : tables + endpoints + fonctions
# Le diag V1 a echoue car la table s'appelle pas 'cycles' et l'endpoint pas /api/cycle/run
from __future__ import annotations
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "api_server.py"
API_STATIC = ROOT / "api_server_with_static.py"
DB = ROOT / "thesium.db"

src = API.read_text(encoding="utf-8-sig") if API.exists() else ""

print("=" * 80)
print("DIAG ELARGI CYCLE / RUN-AGENTS")
print("=" * 80)

# ---------------------------------------------------------------------------
# 1. Toutes les tables (pour reperer celle qui stocke les cycles)
# ---------------------------------------------------------------------------
print("\n--- Toutes les tables DB (>= 1 row) ---")
cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    rows = cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for r in rows:
        t = r["name"]
        try:
            cnt = cx.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            if cnt > 0:
                # Detecter si la table a une colonne created_at / cycle_id
                cols = [c["name"] for c in cx.execute(f"PRAGMA table_info({t})").fetchall()]
                hint = ""
                if "cycle_id" in cols: hint += " [cycle_id]"
                if "created_at" in cols: hint += " [created_at]"
                if "started_at" in cols: hint += " [started_at]"
                if "status" in cols: hint += " [status]"
                print(f"  {t:35} {cnt:6} rows{hint}")
        except Exception:
            pass
finally:
    cx.close()

# ---------------------------------------------------------------------------
# 2. Cycle_reconciliation_log a un cycle_id "20260526-091436" -> chercher la source
# ---------------------------------------------------------------------------
print("\n--- Tables qui ont une colonne cycle_id ---")
cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    rows = cx.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for r in rows:
        t = r["name"]
        try:
            cols = [c["name"] for c in cx.execute(f"PRAGMA table_info({t})").fetchall()]
            if "cycle_id" in cols:
                cnt = cx.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                distinct = cx.execute(f"SELECT COUNT(DISTINCT cycle_id) AS n FROM {t}").fetchone()["n"]
                print(f"  {t}: {cnt} rows, {distinct} cycle_id distincts")
                # 5 derniers cycle_id distincts
                last_ids = cx.execute(
                    f"SELECT DISTINCT cycle_id FROM {t} ORDER BY cycle_id DESC LIMIT 5"
                ).fetchall()
                for lid in last_ids:
                    print(f"    {lid['cycle_id']}")
        except Exception:
            pass
finally:
    cx.close()

# ---------------------------------------------------------------------------
# 3. Tous les endpoints API
# ---------------------------------------------------------------------------
print("\n--- TOUS les endpoints API ---")
for m in re.finditer(r"@app\.(get|post|delete|put)\(['\"]([^'\"]+)['\"]", src):
    print(f"  {m.group(1).upper():5} {m.group(2)}")

# ---------------------------------------------------------------------------
# 4. Fonctions liees au cycle / run / decision
# ---------------------------------------------------------------------------
print("\n--- Fonctions cycle/run/decision/agents ---")
for m in re.finditer(r"^(?:async\s+)?def\s+(\w*(?:cycle|run|decision|agents|reconciliation|propose)\w*)\(", src, re.MULTILINE):
    line_no = src[: m.start()].count("\n") + 1
    print(f"  L{line_no:5} def {m.group(1)}()")

# ---------------------------------------------------------------------------
# 5. Recherche du texte 'cycle_id' dans api_server.py
# ---------------------------------------------------------------------------
print("\n--- 'cycle_id' dans api_server.py (10 premiers) ---")
matches = list(re.finditer(r"cycle_id", src))
for m in matches[:10]:
    line_no = src[: m.start()].count("\n") + 1
    line = src.splitlines()[line_no - 1].strip()
    print(f"  L{line_no:5}: {line[:120]}")
print(f"  ({len(matches)} occurrences total)")

# ---------------------------------------------------------------------------
# 6. Localiser api_server_with_static.py
# ---------------------------------------------------------------------------
print("\n--- api_server_with_static.py (mount static / FileResponse) ---")
if API_STATIC.exists():
    src2 = API_STATIC.read_text(encoding="utf-8-sig")
    for kw in ("StaticFiles", "mount", "FileResponse", "directory=", ".html"):
        for m in re.finditer(re.escape(kw), src2):
            line_no = src2[: m.start()].count("\n") + 1
            line = src2.splitlines()[line_no - 1].strip()
            print(f"  L{line_no:5}: {line[:140]}")
            break  # une seule occurrence par kw
else:
    print(f"  Fichier {API_STATIC.name} introuvable")

# ---------------------------------------------------------------------------
# 7. Fichiers HTML/JS dans le dossier ThesiumDesk
# ---------------------------------------------------------------------------
print("\n--- Fichiers HTML dans ThesiumDesk (et sous-dossiers) ---")
for f in sorted(ROOT.rglob("*.html")):
    size = f.stat().st_size
    rel = f.relative_to(ROOT)
    print(f"  {str(rel):60} {size:>8} bytes")

print("\n--- Fichiers JS dans ThesiumDesk ---")
for f in sorted(ROOT.rglob("*.js")):
    if "node_modules" in str(f) or ".venv" in str(f):
        continue
    size = f.stat().st_size
    rel = f.relative_to(ROOT)
    print(f"  {str(rel):60} {size:>8} bytes")
