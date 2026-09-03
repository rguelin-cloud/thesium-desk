# -*- coding: utf-8 -*-
# [DIAG_TUPLE_INDICES_EXECUTE_V1]
# Identifie OU dans approve_and_fill_order / _update_position / refresh_portfolio_state
# on fait row["xxx"] sans avoir mis conn.row_factory = sqlite3.Row
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def read(p):
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

# 1) execution_engine.py : chercher _update_position et refresh_portfolio_state
section("1) PaperBroker._update_position body")
src = read(os.path.join(ROOT, "execution_engine.py"))
m = re.search(r"def\s+_update_position\s*\(", src)
if m:
    lines = src[m.start():].splitlines()[:80]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")
else:
    print("FAIL: _update_position introuvable")

section("2) refresh_portfolio_state body")
m = re.search(r"def\s+refresh_portfolio_state\s*\(", src)
if m:
    lines = src[m.start():].splitlines()[:80]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")
else:
    print("FAIL: refresh_portfolio_state introuvable")

# 2) Verifier acces row["xxx"] dans ces fonctions
section("3) Acces dict-style sur conn.execute().fetchone() dans execution_engine.py")
for i, ln in enumerate(src.splitlines(), 1):
    if '["' in ln and ('row[' in ln or 'pos[' in ln or 'r[' in ln):
        print(f"  L{i}: {ln.strip()}")

# 3) log_event signature
section("4) log_event signature")
m = re.search(r"def\s+log_event\s*\([^)]*\)\s*:", src)
if m:
    lines = src[m.start():].splitlines()[:30]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")

# 4) row_factory dans execution_engine.py ?
section("5) row_factory dans execution_engine.py")
for i, ln in enumerate(src.splitlines(), 1):
    if "row_factory" in ln:
        print(f"  L{i}: {ln.strip()}")

# 5) endpoint actuel : a-t-il row_factory ?
section("6) endpoint execute : ouverture conn")
src2 = read(os.path.join(ROOT, "api_server_with_static.py"))
m = re.search(r'@app\.post\(\s*["\']\s*/api/orders/\{order_id\}/execute', src2)
if m:
    lines = src2[m.start():].splitlines()[:25]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")

print("\n[DONE]")
