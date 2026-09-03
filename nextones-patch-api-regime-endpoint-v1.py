# -*- coding: utf-8 -*-
"""
Patch 1/2 : ajoute l'endpoint GET /api/regime/current dans
api_server_with_static.py, AVANT app.mount('/', StaticFiles).

Retourne JSON :
{
  "cycle_id": "...", "portfolio_regime": "MAINTAIN",
  "invested_pct": 53.4, "nav": 966331.13, "created_at": "...",
  "equity": {"regime": "NORMAL", "vix": 22.22, "vol_pct": 19.06,
             "dd_pct": -0.20, "buy_mult": 1.0, "sell_mult": 1.0,
             "signals": {"vix": "STRESS", "vol": "NORMAL", "dd": "CALM",
                         "n_calm": 1, "n_stress": 1}},
  "crypto": {"regime": "CALM", ...}
}

Marker idempotent : [PATCH_API_REGIME_CURRENT_V1]
"""
import ast
import os
import py_compile
import re
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")
MARKER = "[PATCH_API_REGIME_CURRENT_V1]"

with open(API, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print(f"[SKIP] Marker {MARKER} deja present.")
    sys.exit(0)

lines = src.splitlines(keepends=True)

# Trouver la ligne app.mount("/" StaticFiles
idx_mount = None
for i, line in enumerate(lines):
    if "app.mount" in line and "StaticFiles" in line and line.strip().startswith("app.mount"):
        idx_mount = i
        break
if idx_mount is None:
    print("[ERR] app.mount('/' StaticFiles) introuvable")
    sys.exit(1)

print(f"[OK] app.mount trouve a L{idx_mount+1}")

# Endpoint a injecter (ASCII pur)
endpoint_code = (
    "\n# " + MARKER + "  ----------------------------------------------------------------\n"
    "@app.get(\"/api/regime/current\")\n"
    "def get_regime_current():\n"
    "    \"\"\"Retourne le dernier cycle regime_log + detail equity/crypto.\n\n"
    "    Lit regime_log (1 ligne) + market_regime_log (2 lignes par cycle).\n"
    "    Fallback gracieux si tables absentes ou pas de donnees.\n"
    "    \"\"\"\n"
    "    import json as _json\n"
    "    import sqlite3 as _sqlite3\n"
    "    from pathlib import Path as _Path\n"
    "    _db_path = str(_Path(__file__).parent / \"thesium.db\")\n"
    "    _resp = {\n"
    "        \"cycle_id\": None, \"portfolio_regime\": None,\n"
    "        \"invested_pct\": None, \"nav\": None, \"created_at\": None,\n"
    "        \"equity\": None, \"crypto\": None,\n"
    "        \"error\": None,\n"
    "    }\n"
    "    try:\n"
    "        _conn = _sqlite3.connect(_db_path)\n"
    "        _conn.row_factory = _sqlite3.Row\n"
    "        _row = _conn.execute(\n"
    "            \"SELECT cycle_id, regime, invested_pct, nav, created_at \"\n"
    "            \"FROM regime_log ORDER BY id DESC LIMIT 1\"\n"
    "        ).fetchone()\n"
    "        if _row:\n"
    "            _resp[\"cycle_id\"] = _row[\"cycle_id\"]\n"
    "            _resp[\"portfolio_regime\"] = _row[\"regime\"]\n"
    "            _resp[\"invested_pct\"] = _row[\"invested_pct\"]\n"
    "            _resp[\"nav\"] = _row[\"nav\"]\n"
    "            _resp[\"created_at\"] = _row[\"created_at\"]\n"
    "            _mrows = _conn.execute(\n"
    "                \"SELECT asset_class, regime, vix_value, realized_vol_pct, \"\n"
    "                \"drawdown_5d_pct, buy_mult, sell_mult, convergence_thresh, \"\n"
    "                \"details_json FROM market_regime_log WHERE cycle_id = ?\",\n"
    "                (_row[\"cycle_id\"],)\n"
    "            ).fetchall()\n"
    "            for _m in _mrows:\n"
    "                try:\n"
    "                    _det = _json.loads(_m[\"details_json\"] or \"{}\")\n"
    "                except Exception:\n"
    "                    _det = {}\n"
    "                _signals = {\n"
    "                    \"vix\": _det.get(\"vix_signal\"),\n"
    "                    \"vol\": _det.get(\"vol_signal\"),\n"
    "                    \"dd\": _det.get(\"dd_signal\"),\n"
    "                    \"n_calm\": _det.get(\"signals_calm\"),\n"
    "                    \"n_stress\": _det.get(\"signals_stress\"),\n"
    "                }\n"
    "                _entry = {\n"
    "                    \"regime\": _m[\"regime\"],\n"
    "                    \"vix\": _m[\"vix_value\"],\n"
    "                    \"vol_pct\": _m[\"realized_vol_pct\"],\n"
    "                    \"dd_pct\": _m[\"drawdown_5d_pct\"],\n"
    "                    \"buy_mult\": _m[\"buy_mult\"],\n"
    "                    \"sell_mult\": _m[\"sell_mult\"],\n"
    "                    \"convergence_thresh\": _m[\"convergence_thresh\"],\n"
    "                    \"signals\": _signals,\n"
    "                }\n"
    "                if _m[\"asset_class\"] == \"equity\":\n"
    "                    _resp[\"equity\"] = _entry\n"
    "                elif _m[\"asset_class\"] == \"crypto\":\n"
    "                    _resp[\"crypto\"] = _entry\n"
    "        _conn.close()\n"
    "    except Exception as _e:\n"
    "        _resp[\"error\"] = str(_e)\n"
    "    return _resp\n"
    "# Fin " + MARKER + "  --------------------------------------------------------------\n\n"
)

# Verif ASCII pur du code injecte
for i, ch in enumerate(endpoint_code):
    if ord(ch) > 127:
        print(f"[ERR] Non-ASCII char dans endpoint_code at pos {i}: U+{ord(ch):04X}")
        sys.exit(20)

# Injection juste avant la ligne app.mount
new_lines = list(lines)
new_lines[idx_mount] = endpoint_code + lines[idx_mount]
new_src = "".join(new_lines)

# AST
try:
    ast.parse(new_src)
    print("[OK] ast.parse passed")
except SyntaxError as e:
    print(f"[ERR] SyntaxError: {e}")
    sys.exit(10)

# Backup + write + py_compile
ts = time.strftime("%Y%m%d-%H%M%S")
backup = API + f".bak.{ts}"
shutil.copyfile(API, backup)
print(f"[OK] Backup -> {backup}")

with open(API, "w", encoding="utf-8", newline="") as f:
    f.write(new_src)
print(f"[OK] {API} reecrit ({new_src.count(chr(10))} lignes)")

try:
    py_compile.compile(API, doraise=True)
    print("[OK] py_compile passed")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile failed: {e}")
    shutil.copyfile(backup, API)
    print(f"[ROLLBACK] depuis {backup}")
    sys.exit(11)

# Verifs
with open(API, "r", encoding="utf-8-sig") as f:
    final = f.read()
print(f"[OK] Marker {MARKER} x{final.count(MARKER)}")
print(f"[OK] @app.get('/api/regime/current') x{final.count('/api/regime/current')}")

print()
print("=" * 70)
print("PATCH ENDPOINT /api/regime/current APPLIQUE")
print("=" * 70)
print("Apres restart API, tester :")
print("  Invoke-RestMethod http://127.0.0.1:8000/api/regime/current | ConvertTo-Json -Depth 6")
