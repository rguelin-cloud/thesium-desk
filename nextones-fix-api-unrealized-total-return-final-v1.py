# -*- coding: utf-8 -*-
# [FIX_API_UNREALIZED_TOTAL_RETURN_FINAL_V1]
# Patch unique api_server.py qui resout :
#   A) _update_portfolio_from_latest_prices : calcule unrealized_pnl + net_capital_flows
#   B) _portfolio_write_with_retry : ecrit unrealized_pnl + unrealized_pnl_pct
#   C) Route /api/dashboard L466-477 : ajoute unrealized_pnl, unrealized_pnl_pct,
#      total_return, total_return_pct dans le dict portfolio
#
# Idempotent (marker). Backup .bak.<ts>. Validation ast + py_compile.

import ast
import py_compile
import sys
import time
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TARGET = BASE / "api_server.py"
MARKER = "# [FIX_API_UNREALIZED_TOTAL_RETURN_FINAL_V1]"

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
        print("SKIP : marker present")
        return 0

    # ============================================================
    # BLOC A : helper _update_portfolio_from_latest_prices
    # ============================================================
    old_a = (
        "        total_cost = sum(u[4] * u[5] for u in updates)\n"
        "        # [TOTAL_PNL_NAV_BASED_V1] NAV-based: inclut realized P&L des SELL passes\n"
        "        # AVANT: total_pnl = total_market_value - total_cost  (unrealized only)\n"
        "        INITIAL_CAPITAL = 1000000\n"
        "        total_pnl = total_value - INITIAL_CAPITAL\n"
        "        total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0\n"
    )
    new_a = (
        "        total_cost = sum(u[4] * u[5] for u in updates)\n"
        "        " + MARKER + " (A)\n"
        "        # Unrealized = market_value - cost_basis (P&L latent des positions ouvertes)\n"
        "        unrealized_pnl = total_market_value - total_cost\n"
        "        INITIAL_CAPITAL = 1000000\n"
        "        # Net capital flows : deposits +, withdrawals -\n"
        "        try:\n"
        "            _fr = conn.execute(\n"
        "                \"SELECT COALESCE(SUM(CASE WHEN flow_type='deposit' THEN amount \"\n"
        "                \"WHEN flow_type='withdrawal' THEN -amount ELSE 0 END), 0) \"\n"
        "                \"FROM capital_flows\"\n"
        "            ).fetchone()\n"
        "            net_capital_flows = _fr[0] if _fr else 0.0\n"
        "        except Exception:\n"
        "            net_capital_flows = 0.0\n"
        "        # Total return (NAV-based) = NAV - initial - flows\n"
        "        total_pnl = total_value - INITIAL_CAPITAL - net_capital_flows\n"
        "        total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0\n"
        "        unrealized_pnl_pct = (unrealized_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0\n"
    )
    if old_a not in src:
        print("ERREUR : bloc A introuvable")
        return 1
    src = src.replace(old_a, new_a, 1)

    # Appel a _portfolio_write_with_retry : ajouter kwargs
    old_call = (
        "        ok = _portfolio_write_with_retry(\n"
        "            conn, today_str, total_value, cash, total_pnl,\n"
        "            total_pnl_pct, daily_pnl, daily_pnl_pct,\n"
        "            max_attempts=3,\n"
        "        )\n"
    )
    new_call = (
        "        ok = _portfolio_write_with_retry(\n"
        "            conn, today_str, total_value, cash, total_pnl,\n"
        "            total_pnl_pct, daily_pnl, daily_pnl_pct,\n"
        "            unrealized_pnl=unrealized_pnl,\n"
        "            unrealized_pnl_pct=unrealized_pnl_pct,\n"
        "            max_attempts=3,\n"
        "        )\n"
    )
    if old_call not in src:
        print("ERREUR : bloc A2 (call helper) introuvable")
        return 1
    src = src.replace(old_call, new_call, 1)

    # ============================================================
    # BLOC B : signature + UPDATE _portfolio_write_with_retry
    # ============================================================
    old_b = (
        "def _portfolio_write_with_retry(conn, today_str, total_value, cash, total_pnl,\n"
        "                                total_pnl_pct, daily_pnl, daily_pnl_pct,\n"
        "                                max_attempts=3):\n"
    )
    new_b = (
        "def _portfolio_write_with_retry(conn, today_str, total_value, cash, total_pnl,\n"
        "                                total_pnl_pct, daily_pnl, daily_pnl_pct,\n"
        "                                unrealized_pnl=None, unrealized_pnl_pct=None,\n"
        "                                max_attempts=3):\n"
    )
    if old_b not in src:
        print("ERREUR : bloc B (signature) introuvable")
        return 1
    src = src.replace(old_b, new_b, 1)

    old_update = (
        "            conn.execute(\n"
        "                \"\"\"UPDATE portfolio_state\n"
        "                   SET total_value=?, total_pnl=?, total_pnl_pct=?,\n"
        "                       daily_pnl=?, daily_pnl_pct=?, updated_at=?\n"
        "                   WHERE id=1\"\"\",\n"
        "                (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4),\n"
        "                 round(daily_pnl, 2), round(daily_pnl_pct, 4),\n"
        "                 datetime.now().isoformat()),\n"
        "            )\n"
    )
    new_update = (
        "            " + MARKER + " (B)\n"
        "            if unrealized_pnl is not None:\n"
        "                conn.execute(\n"
        "                    \"\"\"UPDATE portfolio_state\n"
        "                       SET total_value=?, total_pnl=?, total_pnl_pct=?,\n"
        "                           unrealized_pnl=?, unrealized_pnl_pct=?,\n"
        "                           daily_pnl=?, daily_pnl_pct=?, updated_at=?\n"
        "                       WHERE id=1\"\"\",\n"
        "                    (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4),\n"
        "                     round(unrealized_pnl, 2),\n"
        "                     round(unrealized_pnl_pct if unrealized_pnl_pct is not None else 0, 4),\n"
        "                     round(daily_pnl, 2), round(daily_pnl_pct, 4),\n"
        "                     datetime.now().isoformat()),\n"
        "                )\n"
        "            else:\n"
        "                conn.execute(\n"
        "                    \"\"\"UPDATE portfolio_state\n"
        "                       SET total_value=?, total_pnl=?, total_pnl_pct=?,\n"
        "                           daily_pnl=?, daily_pnl_pct=?, updated_at=?\n"
        "                       WHERE id=1\"\"\",\n"
        "                    (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4),\n"
        "                     round(daily_pnl, 2), round(daily_pnl_pct, 4),\n"
        "                     datetime.now().isoformat()),\n"
        "                )\n"
    )
    if old_update not in src:
        print("ERREUR : bloc B2 (UPDATE) introuvable")
        return 1
    src = src.replace(old_update, new_update, 1)

    # ============================================================
    # BLOC C : route /api/dashboard - dict portfolio L466-477
    # ============================================================
    old_c = (
        "        return {\n"
        "            \"portfolio\": {\n"
        "                \"cash\":           round(ps.get(\"cash\", 0), 2),\n"
        "                \"total_value\":    round(ps.get(\"total_value\", 0), 2),\n"
        "                \"total_pnl\":      round(ps.get(\"total_pnl\", 0), 2),\n"
        "                \"total_pnl_pct\":  round(ps.get(\"total_pnl_pct\", 0), 4),\n"
        "                \"daily_pnl\":      round(ps.get(\"daily_pnl\", 0), 2),\n"
        "                \"daily_pnl_pct\":  round(ps.get(\"daily_pnl_pct\", 0), 4),\n"
        "                \"var_95\":         round(ps.get(\"var_95\", 0), 3),\n"
        "                \"max_drawdown\":   round(ps.get(\"max_drawdown\", 0), 4),\n"
        "                \"updated_at\":     ps.get(\"updated_at\"),\n"
        "            },\n"
        "            \"positions\": positions,\n"
    )
    new_c = (
        "        " + MARKER + " (C)\n"
        "        _upnl = ps.get(\"unrealized_pnl\")\n"
        "        if _upnl is None:\n"
        "            # Fallback : recompute depuis positions si DB pas a jour\n"
        "            _upnl = sum((p.get(\"unrealized_pnl\") or 0) for p in positions)\n"
        "        _upnl_pct = ps.get(\"unrealized_pnl_pct\")\n"
        "        if _upnl_pct is None:\n"
        "            _upnl_pct = (_upnl / 1000000.0 * 100.0) if _upnl else 0.0\n"
        "        _total_pnl = ps.get(\"total_pnl\", 0) or 0\n"
        "        _total_pnl_pct = ps.get(\"total_pnl_pct\", 0) or 0\n"
        "        return {\n"
        "            \"portfolio\": {\n"
        "                \"cash\":               round(ps.get(\"cash\", 0), 2),\n"
        "                \"total_value\":        round(ps.get(\"total_value\", 0), 2),\n"
        "                \"total_pnl\":          round(_total_pnl, 2),\n"
        "                \"total_pnl_pct\":      round(_total_pnl_pct, 4),\n"
        "                \"unrealized_pnl\":     round(_upnl, 2),\n"
        "                \"unrealized_pnl_pct\": round(_upnl_pct, 4),\n"
        "                \"total_return\":       round(_total_pnl, 2),\n"
        "                \"total_return_pct\":   round(_total_pnl_pct, 4),\n"
        "                \"daily_pnl\":          round(ps.get(\"daily_pnl\", 0), 2),\n"
        "                \"daily_pnl_pct\":      round(ps.get(\"daily_pnl_pct\", 0), 4),\n"
        "                \"var_95\":             round(ps.get(\"var_95\", 0), 3),\n"
        "                \"max_drawdown\":       round(ps.get(\"max_drawdown\", 0), 4),\n"
        "                \"updated_at\":         ps.get(\"updated_at\"),\n"
        "            },\n"
        "            \"positions\": positions,\n"
    )
    if old_c not in src:
        print("ERREUR : bloc C (dict /api/dashboard) introuvable")
        return 1
    src = src.replace(old_c, new_c, 1)

    # ============================================================
    # Validation + ecriture
    # ============================================================
    try:
        ast.parse(src)
    except SyntaxError as e:
        print("ERREUR ast.parse : " + str(e))
        return 1

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET.with_suffix(".py.bak." + ts)
    write_text(bak, read_text(TARGET))
    write_text(TARGET, src)
    print("BACKUP : " + bak.name)

    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as e:
        print("ERREUR py_compile : " + str(e))
        write_text(TARGET, read_text(bak))
        print("ROLLBACK")
        return 1

    print("OK : api_server.py patche")
    print("  - A : unrealized_pnl calcule dans helper + capital_flows lookup")
    print("  - B : UPDATE portfolio_state ecrit unrealized_pnl + unrealized_pnl_pct")
    print("  - C : /api/dashboard expose unrealized_pnl, unrealized_pnl_pct, total_return, total_return_pct")
    return 0

if __name__ == "__main__":
    sys.exit(main())
