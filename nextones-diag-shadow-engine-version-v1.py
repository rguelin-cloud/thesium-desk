"""Verifier la version reelle de shadow_engine.py sur disque."""
import os, hashlib, re

path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\shadow_engine.py"
print(f"path = {path}")
print(f"exists = {os.path.exists(path)}")
print(f"size = {os.path.getsize(path)}")
print(f"mtime = {os.path.getmtime(path)}")

with open(path, "rb") as f:
    data = f.read()
print(f"sha256 = {hashlib.sha256(data).hexdigest()[:16]}")

text = data.decode("utf-8", errors="replace")

# Chercher la condition forced_exit
print("\n[Lignes contenant 'fe == 1' ou 'forced exit']")
for i, ln in enumerate(text.split("\n"), 1):
    if "fe == 1" in ln or "Forced exit" in ln or "EPSILON" in ln or "s_fe" in ln:
        print(f"  L{i:3d}: {ln.rstrip()}")

# Pycache
pycache = os.path.join(os.path.dirname(path), "__pycache__")
print(f"\n[__pycache__]")
if os.path.exists(pycache):
    for f in os.listdir(pycache):
        if "shadow" in f:
            p = os.path.join(pycache, f)
            print(f"  {f} mtime={os.path.getmtime(p)} size={os.path.getsize(p)}")
else:
    print("  pas de __pycache__")
