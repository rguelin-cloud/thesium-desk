"""Inspecter MarketDataAdapter dans replay_adapters.py"""
import os, re
PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\replay_adapters.py"
print(f"path = {PATH}")
print(f"exists = {os.path.exists(PATH)}")
print(f"size = {os.path.getsize(PATH)}")
with open(PATH, "rb") as f:
    text = f.read().decode("utf-8", errors="replace")
lines = text.splitlines()
print(f"lines = {len(lines)}")

# Lister classes et def
print("\n[Classes + top-level defs]")
for m in re.finditer(r"^(class|def)\s+\w+[^:]*:", text, re.MULTILINE):
    start = m.start()
    end = text.find("\n", start)
    print(f"  L{text[:start].count(chr(10))+1:3d}: {text[start:end][:130]}")

# Cherche MarketDataAdapter
print("\n[MarketDataAdapter class body]")
m = re.search(r"class\s+MarketDataAdapter[^:]*:", text)
if m:
    start_line = text[:m.start()].count("\n") + 1
    # afficher 80 lignes a partir de la
    for i, ln in enumerate(lines[start_line-1:start_line+80], start_line):
        print(f"  {i:3d}| {ln[:140]}")
