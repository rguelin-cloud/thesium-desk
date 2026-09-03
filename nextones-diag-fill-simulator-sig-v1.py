"""Inspecter fill_simulator.py (jalon 8B.3) pour identifier la signature simulate_fill / simulate_fills."""
import os, re

PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\fill_simulator.py"

if not os.path.exists(PATH):
    print(f"NOT FOUND : {PATH}")
    # chercher dans tout l arbre
    base = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
    for root, dirs, files in os.walk(base):
        if "venv" in root or "__pycache__" in root or "backup" in root.lower():
            continue
        for f in files:
            if f.startswith("fill_") and f.endswith(".py"):
                p = os.path.join(root, f)
                print(f"  candidate : {p} size={os.path.getsize(p)}")
else:
    sz = os.path.getsize(PATH)
    print(f"path = {PATH}")
    print(f"size = {sz}")
    with open(PATH, "rb") as f:
        data = f.read()
    text = data.decode("utf-8", errors="replace")
    print(f"lines = {len(text.splitlines())}")
    print(f"non-ASCII bytes = {sum(1 for b in data if b > 127)}")
    
    # Lister toutes les def
    print("\n[Definitions]")
    for m in re.finditer(r"^(def|class)\s+\w+[^:]*:", text, re.MULTILINE):
        # ligne complete
        start = m.start()
        end = text.find("\n", start)
        print(f"  {text[start:end][:130]}")
    
    # Lister les imports
    print("\n[Imports]")
    for ln in text.splitlines()[:30]:
        if ln.startswith("import") or ln.startswith("from"):
            print(f"  {ln}")
    
    # Header docstring
    print("\n[Docstring header / 60 first lines]")
    for i, ln in enumerate(text.splitlines()[:60], 1):
        print(f"  {i:3d}| {ln[:130]}")
