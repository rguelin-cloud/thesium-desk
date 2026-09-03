# -*- coding: utf-8 -*-
# [FIX_CRYPTO_PRICES_NAV_BASED_V1]
# Patche fix_crypto_prices.py pour:
#  - ne plus ecraser total_pnl avec unrealized only (current - cost)
#  - calculer total_pnl = NAV - INITIAL_CAPITAL - net_capital_flows (coherent api_server)
#  - aussi ecrire unrealized_pnl + unrealized_pnl_pct dans portfolio_state
#
# Idempotent : skip si marker present.

import ast
import py_compile
import re
import shutil
import time
from pathlib import Path

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\fix_crypto_prices.py")
MARKER = "FIX_CRYPTO_PRICES_NAV_BASED_V1"

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")

def write_text(p, text):
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))

src = read_text(TARGET)

if MARKER in src:
    print(f"[SKIP] marker {MARKER} deja present")
    raise SystemExit(0)

# Backup
ts = time.strftime("%Y%m%d_%H%M%S")
backup = TARGET.with_suffix(f".py.bak.{ts}")
shutil.copy2(TARGET, backup)
print(f"[OK] backup -> {backup.name}")

# Le bloc cible (L187-195) :
#   total_cost = sum(r["quantity"] * r["avg_cost"] for r in rows if r["quantity"])
#   total_pnl = total_market_value - total_cost
#   total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
#
#   conn.execute("""UPDATE portfolio_state
#       SET total_value=?, total_pnl=?, total_pnl_pct=?, updated_at=datetime('now')
#       WHERE id=1""",
#       (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4)))
#
# On remplace ce bloc complet par une version NAV-based.

old_block_rgx = re.compile(
    r'total_cost\s*=\s*sum\(.*?\)\s*\n'
    r'\s*total_pnl\s*=\s*total_market_value\s*-\s*total_cost\s*\n'
    r'\s*total_pnl_pct\s*=\s*\(.*?\)\s*if\s+total_cost\s+else\s+0\s*\n'
    r'\s*\n?'
    r'\s*conn\.execute\(\"\"\"UPDATE\s+portfolio_state\s*\n'
    r'\s*SET\s+total_value=\?\s*,\s*total_pnl=\?\s*,\s*total_pnl_pct=\?\s*,\s*updated_at=datetime\(\'now\'\)\s*\n'
    r'\s*WHERE\s+id=1\"\"\"\s*,\s*\n'
    r'\s*\(round\(total_value,\s*2\)\s*,\s*round\(total_pnl,\s*2\)\s*,\s*round\(total_pnl_pct,\s*4\)\)\)',
    re.DOTALL,
)

m = old_block_rgx.search(src)
if not m:
    print("[ERR] bloc cible introuvable - tentative pattern simplifie")
    # Pattern plus permissif
    simple_rgx = re.compile(
        r'total_pnl\s*=\s*total_market_value\s*-\s*total_cost.*?'
        r'\(round\(total_value,\s*2\)\s*,\s*round\(total_pnl,\s*2\)\s*,\s*round\(total_pnl_pct,\s*4\)\)\)',
        re.DOTALL,
    )
    m = simple_rgx.search(src)
    if not m:
        print("[ERR] aucun pattern matche - abort")
        raise SystemExit(1)
    print("[OK] pattern simplifie a matche")
else:
    print("[OK] pattern principal a matche")

new_block = (
    '# [FIX_CRYPTO_PRICES_NAV_BASED_V1] NAV-based total_pnl + unrealized separe\n'
    '    total_cost = sum(r["quantity"] * r["avg_cost"] for r in rows if r["quantity"])\n'
    '    unrealized_pnl = total_market_value - total_cost\n'
    '    unrealized_pnl_pct = (unrealized_pnl / total_cost * 100) if total_cost else 0\n'
    '    \n'
    '    # Total P&L = NAV - INITIAL_CAPITAL - net_capital_flows\n'
    '    INITIAL_CAPITAL = 1_000_000.0\n'
    '    try:\n'
    '        cur_nf = conn.execute(\n'
    '            "SELECT COALESCE(SUM(CASE WHEN side=\'deposit\' THEN amount END), 0) - "\n'
    '            "COALESCE(SUM(CASE WHEN side=\'withdrawal\' THEN amount END), 0) FROM capital_flows"\n'
    '        )\n'
    '        net_flows = float(cur_nf.fetchone()[0] or 0)\n'
    '    except Exception:\n'
    '        net_flows = 0.0\n'
    '    \n'
    '    total_pnl = total_value - INITIAL_CAPITAL - net_flows\n'
    '    base_pct = INITIAL_CAPITAL + net_flows\n'
    '    total_pnl_pct = (total_pnl / base_pct * 100) if base_pct > 0 else 0\n'
    '    \n'
    '    conn.execute("""UPDATE portfolio_state\n'
    '        SET total_value=?, total_pnl=?, total_pnl_pct=?,\n'
    '            unrealized_pnl=?, unrealized_pnl_pct=?,\n'
    '            updated_at=datetime(\'now\')\n'
    '        WHERE id=1""",\n'
    '        (round(total_value, 2), round(total_pnl, 2), round(total_pnl_pct, 4),\n'
    '         round(unrealized_pnl, 2), round(unrealized_pnl_pct, 4)))'
)

src_new = src[:m.start()] + new_block + src[m.end():]

# Validation AST
try:
    ast.parse(src_new)
except SyntaxError as e:
    broken = TARGET.with_suffix(".py.broken")
    write_text(broken, src_new)
    print(f"[ERR] AST parse failed : {e}")
    print(f"      Broken -> {broken.name}")
    raise SystemExit(2)

write_text(TARGET, src_new)
try:
    py_compile.compile(str(TARGET), doraise=True)
    print("[OK] py_compile passed")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile failed : {e}")
    raise SystemExit(3)

print(f"[OK] fix_crypto_prices.py patche avec marker [{MARKER}]")
print(f"[OK] backup : {backup.name}")
print()
print("Effet : ce script ecrit desormais")
print("  total_pnl = total_value - 1M - net_flows  (= NAV-based, coherent api_server)")
print("  unrealized_pnl = total_market_value - total_cost  (= ce qui etait dans total_pnl avant)")
print("  unrealized_pnl_pct = unrealized_pnl / total_cost * 100")
print()
print("DONE [FIX_CRYPTO_PRICES_NAV_BASED_V1]")
