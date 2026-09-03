# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-METAAPI-PROVIDER-V1]
# Inspecte le module metaapi_provider deja existant :
#  - localise le fichier
#  - liste les fonctions publiques exposees
#  - cherche une fonction pour fetch les POSITIONS ouvertes
#  - teste is_configured() pour savoir si les credentials sont en place

import os
import re
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, PROD_DIR)


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


# ----------------------------- 1 -----------------------------
banner("[1] Localise metaapi_provider")
mp_path = None
for f in os.listdir(PROD_DIR):
    if f in ("metaapi_provider.py", "metaapi_provider"):
        mp_path = os.path.join(PROD_DIR, f)
        break

if mp_path is None:
    # Cherche en profondeur
    for root, dirs, files in os.walk(PROD_DIR):
        dirs[:] = [d for d in dirs if d not in (
            "__pycache__", ".git", "node_modules", "venv", ".venv"
        )]
        if "metaapi_provider.py" in files:
            mp_path = os.path.join(root, "metaapi_provider.py")
            break

if mp_path is None:
    print("  [FAIL] metaapi_provider.py introuvable")
    sys.exit(1)

print(f"  [OK] {mp_path}")
print(f"  taille : {os.path.getsize(mp_path):,} bytes")


# ----------------------------- 2 -----------------------------
banner("[2] Imports et toutes les defs (signatures)")
with open(mp_path, "r", encoding="utf-8-sig") as f:
    src = f.read()

print(f"  lignes : {src.count(chr(10))+1}")

print("\n  --- IMPORTS ---")
for ln in src.split("\n")[:50]:
    if ln.startswith("import ") or ln.startswith("from "):
        print(f"    {ln}")

print("\n  --- DEFS (toutes) ---")
defs = re.findall(
    r"^(?P<indent>[ \t]*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)",
    src, re.MULTILINE
)
for indent, name, args in defs:
    if indent != "":  # methodes de classe, on saute
        continue
    args_short = re.sub(r"\s+", " ", args)[:120]
    print(f"    {name}({args_short})")

print("\n  --- CLASSES ---")
classes = re.findall(r"^class\s+(\w+)", src, re.MULTILINE)
for c in classes:
    print(f"    class {c}")


# ----------------------------- 3 -----------------------------
banner("[3] Cherche les fonctions liees aux POSITIONS")
position_pats = [
    r"^(?:async\s+)?def\s+\w*position\w*\s*\(",
    r"^(?:async\s+)?def\s+get_positions",
    r"^(?:async\s+)?def\s+list_positions",
    r"^(?:async\s+)?def\s+\w*orders\w*\s*\(",
    r"\.get_positions\(",
    r"\.list_positions\(",
    r"terminal_state",
]
for pat in position_pats:
    for m in re.finditer(pat, src, re.MULTILINE):
        ln_no = src[:m.start()].count("\n") + 1
        ln = src.split("\n")[ln_no - 1].strip()
        print(f"  L{ln_no:4} | {ln[:120]}")


# ----------------------------- 4 -----------------------------
banner("[4] Variables d'environnement attendues")
env_pat = re.compile(r"(?:os\.getenv|os\.environ\[?)?\s*\(?\s*['\"]([A-Z_]+)['\"]")
mentioned = set()
for m in env_pat.finditer(src):
    v = m.group(1)
    if any(k in v for k in ["META", "ACCOUNT", "TOKEN", "REGION", "BROKER", "MT5"]):
        mentioned.add(v)
print(f"  variables reperees : {sorted(mentioned)}")


# ----------------------------- 5 -----------------------------
banner("[5] Test is_configured() en live")
try:
    import metaapi_provider as mp
    cfg = mp.is_configured() if hasattr(mp, "is_configured") else None
    print(f"  is_configured() = {cfg}")
    if hasattr(mp, "__all__"):
        print(f"  __all__ = {mp.__all__}")
    # Liste les attributs publics
    public_attrs = [a for a in dir(mp) if not a.startswith("_")]
    print(f"  attributs publics ({len(public_attrs)}) :")
    for a in public_attrs:
        try:
            obj = getattr(mp, a)
            kind = type(obj).__name__
            print(f"    {a:30} ({kind})")
        except Exception:
            print(f"    {a:30} (?)")
except Exception as e:
    print(f"  [FAIL] import : {e}")


# ----------------------------- 6 -----------------------------
banner("[6] Si is_configured False, montre pourquoi (corps de is_configured)")
m = re.search(
    r"def\s+is_configured\s*\([^)]*\)[^:]*:\s*\n((?:    .*\n|\s*\n)+)",
    src, re.MULTILINE
)
if m:
    body = m.group(1)
    print(body[:600])

print()
print("[DONE]")
