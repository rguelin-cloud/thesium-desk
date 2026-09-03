# [DIAG_RUN_CYCLE_LOCK_V1] Inspecte le scheduler + endpoint /api/cycle/run
# Repond a la question: pourquoi RUN CYCLE peut s'executer plusieurs fois par jour ?
#
# Verifie:
#   - Tous les jobs APScheduler dans api_server.py
#   - L'endpoint /api/cycle/run (manual trigger ?)
#   - Presence d'un verrou (lock file, DB flag, etc.)
#   - Historique des cycles dans la table runs/cycles
from __future__ import annotations
import re
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = ROOT / "api_server.py"
DB = ROOT / "thesium.db"

print("=" * 80)
print("DIAG RUN_CYCLE LOCK")
print("=" * 80)

# ---------------------------------------------------------------------------
# 1. Scan api_server.py pour tous les jobs scheduler + endpoints cycle
# ---------------------------------------------------------------------------
src = API.read_text(encoding="utf-8-sig")

print("\n--- Jobs APScheduler (add_job) ---")
for m in re.finditer(r"scheduler\.add_job\([^)]+\)", src, re.DOTALL):
    snippet = m.group(0).replace("\n", " ").strip()
    snippet = re.sub(r"\s+", " ", snippet)
    print(f"  {snippet[:200]}")

print("\n--- Endpoints contenant 'cycle' ---")
for m in re.finditer(r"@app\.(get|post)\(['\"]([^'\"]*cycle[^'\"]*)['\"]\)", src):
    method = m.group(1).upper()
    route = m.group(2)
    print(f"  {method:5} {route}")

print("\n--- Fonctions run_*_cycle / decision_cycle ---")
for m in re.finditer(r"^(?:async\s+)?def\s+(\w*(?:cycle|decision)\w*)\(", src, re.MULTILINE):
    print(f"  def {m.group(1)}()")

print("\n--- Recherche d'un verrou (lock, mutex, semaphore) ---")
patterns = [
    r"cycle.*lock", r"lock.*cycle",
    r"is_running", r"already_running",
    r"\.lock", r"Lock\(\)",
    r"once_per_day", r"daily_lock",
]
found_lock = False
for pat in patterns:
    for m in re.finditer(pat, src, re.IGNORECASE):
        line_no = src[: m.start()].count("\n") + 1
        line = src.splitlines()[line_no - 1].strip()
        print(f"  L{line_no}: {line[:120]}")
        found_lock = True
if not found_lock:
    print("  AUCUN VERROU DETECTE - le cycle peut etre relance a volonte")

# ---------------------------------------------------------------------------
# 2. Inspecter la DB : tables runs / cycles / decision_cycles
# ---------------------------------------------------------------------------
print("\n--- Tables DB liees aux cycles ---")
cx = sqlite3.connect(str(DB), timeout=10)
cx.row_factory = sqlite3.Row
try:
    tables = [r["name"] for r in cx.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%cycle%'"
    ).fetchall()]
    print(f"  Tables trouvees: {tables}")

    for t in tables:
        try:
            cnt = cx.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
            print(f"\n  Table {t}: {cnt} rows")
            # 5 derniers cycles
            cols = [c["name"] for c in cx.execute(f"PRAGMA table_info({t})").fetchall()]
            print(f"    Colonnes: {cols}")
            order_col = "id"
            for c in ("created_at", "ts", "started_at", "id"):
                if c in cols:
                    order_col = c
                    break
            rows = cx.execute(f"SELECT * FROM {t} ORDER BY {order_col} DESC LIMIT 5").fetchall()
            for r in rows:
                d = dict(r)
                short = {k: (str(v)[:40] if v else v) for k, v in d.items() if k in ("id", "status", "created_at", "started_at", "ended_at", "ts")}
                print(f"    {short}")
        except Exception as e:
            print(f"    ERREUR {t}: {e}")
finally:
    cx.close()

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("""
Si aucun verrou n'est detecte ci-dessus, c'est NORMAL que le cycle puisse tourner
plusieurs fois par jour :
  - Le bouton UI /api/cycle/run declenche un cycle manuellement
  - APScheduler declenche aussi des cycles automatiques (cron / interval)
  - Aucun garde-fou "1 cycle / jour max"

Si tu veux limiter a 1 cycle / jour, il faut :
  1. Ajouter une colonne `cycle_date` dans la table cycles
  2. Refuser /api/cycle/run si un cycle existe deja pour la date du jour
  3. OU desactiver le declencheur manuel et garder seulement le job scheduler
""")
