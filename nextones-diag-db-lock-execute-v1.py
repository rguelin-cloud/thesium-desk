# -*- coding: utf-8 -*-
# [DIAG_DB_LOCK_EXECUTE_V1]
# Identifie la source des verrous "database is locked" sur POST /api/orders/{id}/execute
# Lit (utf-8-sig), pas d'ecriture, ASCII pur
import io, os, re, sys, ast

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def read(p):
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

# 1) Reperer approve_and_fill_order dans execution_engine.py
section("1) execution_engine.py : approve_and_fill_order body")
ep = os.path.join(ROOT, "execution_engine.py")
src = read(ep)
m = re.search(r"def\s+approve_and_fill_order\s*\([^)]*\)\s*:", src)
if not m:
    print("FAIL: approve_and_fill_order introuvable")
else:
    start = m.start()
    # capturer ~120 lignes apres
    lines = src[start:].splitlines()[:120]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")

# 2) Cherche toutes les ouvertures sqlite3.connect avec/sans busy_timeout
section("2) execution_engine.py : sqlite3.connect + PRAGMA")
for i, ln in enumerate(src.splitlines(), 1):
    if "sqlite3.connect" in ln or "busy_timeout" in ln or "journal_mode" in ln or "PRAGMA" in ln.upper():
        print(f"  L{i}: {ln.strip()}")

# 3) api_server.py : pattern _portfolio_write_with_retry (deja existant)
section("3) api_server.py : pattern _portfolio_write_with_retry")
ap = os.path.join(ROOT, "api_server.py")
asrc = read(ap)
m2 = re.search(r"def\s+_portfolio_write_with_retry\s*\([^)]*\)\s*:", asrc)
if m2:
    start = m2.start()
    lines = asrc[start:].splitlines()[:60]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")
else:
    print("FAIL: _portfolio_write_with_retry introuvable")

# 4) api_server_with_static.py : endpoint /api/orders/{id}/execute body
section("4) api_server_with_static.py : endpoint execute")
aps = os.path.join(ROOT, "api_server_with_static.py")
asrc2 = read(aps)
m3 = re.search(r'@app\.post\(\s*["\']\s*/api/orders/\{order_id\}/execute', asrc2)
if m3:
    start = m3.start()
    lines = asrc2[start:].splitlines()[:50]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")
else:
    print("FAIL: endpoint /api/orders/{id}/execute introuvable")

# 5) auth.py : authenticate_user (login locked aussi)
section("5) auth.py : authenticate_user connect")
authp = os.path.join(ROOT, "auth.py")
authsrc = read(authp)
ma = re.search(r"def\s+authenticate_user\s*\(", authsrc)
if ma:
    start = ma.start()
    lines = authsrc[start:].splitlines()[:40]
    for i, ln in enumerate(lines, 1):
        print(f"L{i:03d}: {ln}")

# 6) Lister TOUS les sqlite3.connect dans le projet root avec timeout
section("6) Tous sqlite3.connect dans .py root (sans timeout = candidat)")
for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".py"):
        continue
    fp = os.path.join(ROOT, fname)
    try:
        s = read(fp)
    except Exception:
        continue
    for i, ln in enumerate(s.splitlines(), 1):
        if "sqlite3.connect" in ln:
            has_to = "timeout" in ln
            mark = "" if has_to else "  <-- SANS TIMEOUT"
            print(f"  {fname}:L{i}: {ln.strip()}{mark}")

print("\n[DONE]")
