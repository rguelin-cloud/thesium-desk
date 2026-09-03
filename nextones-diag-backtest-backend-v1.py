"""
Diag backtest backend : trouve endpoint(s) et module(s) backtest cote serveur.
ASCII pur. Read utf-8-sig, no write.
"""
import io, os, re, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def rd(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

print("=" * 70)
print("DIAG BACKTEST BACKEND")
print("=" * 70)

# 1) Routes /api/backtest* dans api_server_with_static.py
api_path = os.path.join(ROOT, "api_server_with_static.py")
if os.path.exists(api_path):
    src = rd(api_path)
    lines = src.splitlines()
    print("\n[1] Routes /api/backtest* dans api_server_with_static.py:")
    for i, ln in enumerate(lines, 1):
        if "backtest" in ln.lower() and ("@app." in ln or "def " in ln or "import" in ln):
            print(f"  L{i}: {ln.rstrip()[:140]}")
else:
    print("  (api_server_with_static.py introuvable)")

# 2) Fichiers backtest* a la racine
print("\n[2] Fichiers *backtest* a la racine:")
for f in sorted(os.listdir(ROOT)):
    if "backtest" in f.lower() and (f.endswith(".py") or f.endswith(".js") or f.endswith(".html")):
        full = os.path.join(ROOT, f)
        size = os.path.getsize(full)
        print(f"  {f}  ({size} bytes)")

# 3) Pour chaque .py backtest, premieres lignes + signatures
print("\n[3] Signatures fonctions des modules backtest:")
for f in sorted(os.listdir(ROOT)):
    if "backtest" in f.lower() and f.endswith(".py"):
        full = os.path.join(ROOT, f)
        try:
            src = rd(full)
        except Exception as e:
            print(f"  (read fail {f}: {e})")
            continue
        print(f"  --- {f} ({len(src.splitlines())} lignes) ---")
        for i, ln in enumerate(src.splitlines(), 1):
            s = ln.strip()
            if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
                print(f"    L{i}: {s[:140]}")

# 4) Reference au front : index.html bloc backtest
idx = os.path.join(ROOT, "index.html")
if os.path.exists(idx):
    src = rd(idx)
    print("\n[4] Bloc 'tab-backtest' dans index.html:")
    m = re.search(r'<section[^>]*id="tab-backtest"[^>]*>', src)
    if m:
        pos = m.start()
        # extract approx 80 lines around
        lines = src.splitlines()
        # find line number
        before = src[:pos].count("\n")
        s = max(0, before - 1)
        e = min(len(lines), before + 80)
        print(f"  Tab section debut L{before+1}")
        # show first 40 lines (header zone)
        for i in range(s, min(s + 40, e)):
            print(f"  L{i+1}: {lines[i].rstrip()[:140]}")
    else:
        print("  (tab-backtest pas trouve)")
print("\nDONE")
