"""
Diag: localise le vrai point d'insertion pour ecrire orders.justification.
- Ou est cree un ordre en base ? (INSERT INTO orders)
- Comment est appelee cette creation (execute_cycle ? approve ? UI direct ?)
- Body de _build_proposed_changes_section (memo_generator.py L147+)
- Endpoint /api/orders/pending_approval body (api_server.py L397+)
"""
import os
import re
import glob

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")
API_ALT = os.path.join(ROOT, "api_server.py")
MEMO_GEN = os.path.join(ROOT, "memo_generator.py")

print("=" * 80)
print("1) TOUTES les INSERT INTO orders (dans le repo)")
print("=" * 80)

py_files = glob.glob(os.path.join(ROOT, "*.py"))
py_files = [f for f in py_files if not os.path.basename(f).startswith("nextones-diag")
            and not os.path.basename(f).startswith("nextones-fix")
            and not os.path.basename(f).startswith("nextones-install")
            and not os.path.basename(f).startswith("nextones-patch")]

pat = re.compile(r"INSERT\s+INTO\s+orders", re.IGNORECASE)
for f in py_files:
    try:
        with open(f, "r", encoding="utf-8-sig", errors="replace") as fh:
            src = fh.read()
        matches = []
        for i, ln in enumerate(src.splitlines(), 1):
            if pat.search(ln):
                matches.append((i, ln.strip()[:200]))
        if matches:
            print(f"\n  {os.path.basename(f)}: {len(matches)} matches")
            for i, ln in matches:
                print(f"    L{i}: {ln}")
    except OSError:
        pass

print()
print("=" * 80)
print("2) Body endpoint /api/orders/pending_approval (api_server_with_static.py L397+)")
print("=" * 80)

if os.path.exists(API):
    with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().splitlines()

    start = None
    for i, ln in enumerate(lines, 1):
        if '/api/orders/pending_approval' in ln:
            start = i
            break

    if start:
        # trouve le prochain @app.get/post ou fin
        end = min(start + 80, len(lines))
        for j in range(start, min(start + 80, len(lines))):
            if j > start and re.match(r"\s*@app\.", lines[j]):
                end = j
                break
        for i in range(start - 1, end):
            ln = lines[i]
            s = ln if len(ln) <= 220 else ln[:220] + "...[TRUNC]"
            print(f"L{i+1}: {s}")
else:
    print("  [ERR] api file missing")

print()
print("=" * 80)
print("3) Body _build_proposed_changes_section (memo_generator.py)")
print("=" * 80)

if os.path.exists(MEMO_GEN):
    with open(MEMO_GEN, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().splitlines()

    start = None
    for i, ln in enumerate(lines, 1):
        if "def _build_proposed_changes_section" in ln:
            start = i
            break

    if start:
        end = min(start + 80, len(lines))
        for j in range(start, min(start + 80, len(lines))):
            if j > start and re.match(r"^def ", lines[j]):
                end = j
                break
        for i in range(start - 1, end):
            ln = lines[i]
            s = ln if len(ln) <= 220 else ln[:220] + "...[TRUNC]"
            print(f"L{i+1}: {s}")
    else:
        print("  [ERR] _build_proposed_changes_section not found")
else:
    print("  [ERR] memo_generator.py missing")

print()
print("=" * 80)
print("4) Endpoints qui ecrivent dans orders (POST) - recherche pattern")
print("=" * 80)

if os.path.exists(API):
    with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
        api_src = f.read()

    # cherche @app.post + orders
    for i, ln in enumerate(api_src.splitlines(), 1):
        if re.search(r'@app\.(post|put)\(.*orders', ln, re.IGNORECASE):
            print(f"  L{i}: {ln.strip()[:220]}")
        if re.search(r'"INSERT INTO orders"', ln, re.IGNORECASE):
            print(f"  L{i}: {ln.strip()[:220]}")

print()
print("=" * 80)
print("5) execution_engine / risk_engine / order_translator - INSERT orders ?")
print("=" * 80)
candidates = ["execution_engine.py", "risk_engine.py", "order_translator.py",
              "broker_shadow_executor.py", "portfolio_construction_agent.py"]
for name in candidates:
    p = os.path.join(ROOT, name)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            src = f.read()
        matches = [(i, ln.strip()[:180]) for i, ln in enumerate(src.splitlines(), 1)
                   if pat.search(ln)]
        print(f"\n  {name}: {len(matches)} INSERT INTO orders match(es)")
        for i, ln in matches[:5]:
            print(f"    L{i}: {ln}")
    else:
        print(f"\n  {name}: NOT FOUND")

print()
print("[DONE]")
