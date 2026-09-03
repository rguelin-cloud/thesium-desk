# -*- coding: utf-8 -*-
# [FIX_RISK_ENGINE_PNL_NAV_BASED_V1]
# Patch risk_engine.py :
#   1. Remplace formule total_pnl L363 par NAV-based avec capital_flows
#   2. Ajoute unrealized_pnl en variable separee
#   3. Etend INSERT OR REPLACE portfolio_state pour ecrire unrealized_pnl + unrealized_pnl_pct
#
# Idempotent : skip si marker present.
# Backup .bak.<timestamp>.

import ast
import py_compile
import re
import sys
import time
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TARGET = BASE / "risk_engine.py"
MARKER = "# [FIX_RISK_ENGINE_PNL_NAV_BASED_V1]"
INITIAL_CAPITAL = 1_000_000

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))

def main():
    src = read_text(TARGET)

    if MARKER in src:
        print("SKIP : marker present, patch deja applique")
        return 0

    # ---------- BLOC 1 : remplacer L362-366 (total_cost_basis + total_pnl + initial_capital) ----------
    # Cible exacte (regex tolere espaces) :
    #   total_cost_basis = sum(...)
    #   total_pnl = total_position_value - total_cost_basis
    #   # FIX ...
    #   initial_capital = 1_000_000
    #   total_pnl_pct = ...
    old_block = re.compile(
        r"    total_cost_basis = sum\(p\[\"quantity\"\] \* p\[\"avg_cost\"\] for p in positions\)\n"
        r"    total_pnl = total_position_value - total_cost_basis\n"
        r"    # FIX : on prend la base initiale \(cash de depart . 1M\) si pas de cost basis\n"
        r"    initial_capital = 1_000_000\n"
        r"    total_pnl_pct = \(total_pnl / initial_capital \* 100\) if initial_capital > 0 else 0\n",
        re.UNICODE
    )
    # Note : le commentaire L364 contient un caractere accentue qu'on doit matcher de facon flexible.
    # Strategie : fallback regex plus permissif si le strict ne match pas.

    if not old_block.search(src):
        # Fallback : regex plus permissif (ne match pas le commentaire exact)
        old_block = re.compile(
            r"    total_cost_basis = sum\(p\[\"quantity\"\] \* p\[\"avg_cost\"\] for p in positions\)\n"
            r"    total_pnl = total_position_value - total_cost_basis\n"
            r"(    #[^\n]*\n)"
            r"    initial_capital = 1_000_000\n"
            r"    total_pnl_pct = \(total_pnl / initial_capital \* 100\) if initial_capital > 0 else 0\n"
        )
        if not old_block.search(src):
            print("ERREUR : bloc 1 (total_pnl) introuvable")
            return 1

    new_block_1 = (
        "    total_cost_basis = sum(p[\"quantity\"] * p[\"avg_cost\"] for p in positions)\n"
        "    " + MARKER + "\n"
        "    # Unrealized = position_value - cost_basis (P&L latent des positions ouvertes)\n"
        "    unrealized_pnl = total_position_value - total_cost_basis\n"
        "    initial_capital = 1_000_000\n"
        "    # Net capital flows : deposits positifs, withdrawals negatifs (table capital_flows)\n"
        "    try:\n"
        "        flows_row = conn.execute(\n"
        "            \"SELECT COALESCE(SUM(CASE WHEN flow_type='deposit' THEN amount \"\n"
        "            \"WHEN flow_type='withdrawal' THEN -amount ELSE 0 END), 0) AS net_flows \"\n"
        "            \"FROM capital_flows\"\n"
        "        ).fetchone()\n"
        "        net_capital_flows = flows_row[\"net_flows\"] if flows_row else 0.0\n"
        "    except Exception:\n"
        "        net_capital_flows = 0.0\n"
        "    # Total return NAV-based : NAV - capital initial - net flows\n"
        "    total_pnl = total_value - initial_capital - net_capital_flows\n"
        "    total_pnl_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0\n"
        "    unrealized_pnl_pct = (unrealized_pnl / initial_capital * 100) if initial_capital > 0 else 0\n"
    )

    src2, n1 = old_block.subn(new_block_1, src, count=1)
    if n1 != 1:
        print("ERREUR : bloc 1 substitution n1=" + str(n1))
        return 1

    # ---------- BLOC 2 : etendre INSERT OR REPLACE portfolio_state ----------
    old_insert = re.compile(
        r"    conn\.execute\(\n"
        r"        \"\"\"INSERT OR REPLACE INTO portfolio_state\n"
        r"               \(id, cash, total_value, total_pnl, total_pnl_pct,\n"
        r"                daily_pnl, daily_pnl_pct, var_95, updated_at\)\n"
        r"           VALUES \(1, \?, \?, \?, \?, \?, \?, \?, \?\)\"\"\",\n"
        r"        \(round\(cash, 2\), round\(total_value, 2\), round\(total_pnl, 2\),\n"
        r"         round\(total_pnl_pct, 4\), round\(daily_pnl, 2\), round\(daily_pnl_pct, 4\),\n"
        r"         var_95, now\)\n"
        r"    \)\n"
    )

    if not old_insert.search(src2):
        print("ERREUR : bloc 2 (INSERT portfolio_state) introuvable")
        return 1

    new_block_2 = (
        "    conn.execute(\n"
        "        \"\"\"INSERT OR REPLACE INTO portfolio_state\n"
        "               (id, cash, total_value, total_pnl, total_pnl_pct,\n"
        "                unrealized_pnl, unrealized_pnl_pct,\n"
        "                daily_pnl, daily_pnl_pct, var_95, updated_at)\n"
        "           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\"\"\",\n"
        "        (round(cash, 2), round(total_value, 2), round(total_pnl, 2),\n"
        "         round(total_pnl_pct, 4),\n"
        "         round(unrealized_pnl, 2), round(unrealized_pnl_pct, 4),\n"
        "         round(daily_pnl, 2), round(daily_pnl_pct, 4),\n"
        "         var_95, now)\n"
        "    )\n"
    )

    src3, n2 = old_insert.subn(new_block_2, src2, count=1)
    if n2 != 1:
        print("ERREUR : bloc 2 substitution n2=" + str(n2))
        return 1

    # ---------- Validation ----------
    try:
        ast.parse(src3)
    except SyntaxError as e:
        print("ERREUR ast.parse : " + str(e))
        return 1

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET.with_suffix(".py.bak." + ts)
    write_text(bak, src)
    print("BACKUP : " + str(bak))

    # Write patched
    write_text(TARGET, src3)

    # py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as e:
        print("ERREUR py_compile : " + str(e))
        # Rollback
        write_text(TARGET, src)
        print("ROLLBACK effectue")
        return 1

    print("OK : risk_engine.py patche (formule NAV-based + unrealized separe)")
    print("  - L363 ancien total_pnl supprime")
    print("  - unrealized_pnl + total_pnl + net_capital_flows lookup ajoutes")
    print("  - INSERT portfolio_state ecrit maintenant unrealized_pnl + unrealized_pnl_pct")
    return 0

if __name__ == "__main__":
    sys.exit(main())
