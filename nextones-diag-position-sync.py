# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-POSITION-SYNC-V1]
# Cartographie position_sync.py pour reprendre le pattern MetaAPI
# en Phase 3B reconciler ActivTrades.
#
# Cherche :
#  - les credentials MetaAPI (token, account_id, region)
#  - les fonctions de fetch positions
#  - les patterns d'erreur / retry
#  - les autres scripts qui appellent MetaAPI (yt-dlp grep style)

import os
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


# ----------------------------- 1 -----------------------------
banner("[1] Recherche fichiers position_sync* et metaapi*")
for f in sorted(os.listdir(PROD_DIR)):
    lf = f.lower()
    if ("position_sync" in lf or "metaapi" in lf or "meta_api" in lf
            or "activtrades" in lf or "mt5" in lf):
        size = os.path.getsize(os.path.join(PROD_DIR, f))
        print(f"  {f:50} ({size:,} bytes)")


# ----------------------------- 2 -----------------------------
banner("[2] Cherche references MetaAPI / META_API / METAAPI dans tous les .py")
import re
pat = re.compile(r"meta_?api|METAAPI|META_API|MetaAPI", re.IGNORECASE)
hits = {}
for root, dirs, files in os.walk(PROD_DIR):
    # Skip node_modules, venv, __pycache__
    dirs[:] = [d for d in dirs if d not in (
        "__pycache__", ".git", "node_modules", "venv", ".venv"
    )]
    for f in files:
        if not f.endswith(".py"):
            continue
        full = os.path.join(root, f)
        try:
            with open(full, "r", encoding="utf-8-sig", errors="ignore") as fp:
                src = fp.read()
        except Exception:
            continue
        n = len(pat.findall(src))
        if n > 0:
            rel = os.path.relpath(full, PROD_DIR)
            hits[rel] = n

for f in sorted(hits.keys(), key=lambda k: -hits[k])[:20]:
    print(f"  {f:60} {hits[f]:3} hits")


# ----------------------------- 3 -----------------------------
banner("[3] Recherche credentials (token, account, login)")
cred_pat = re.compile(
    r"(METAAPI_TOKEN|METAAPI_ACCOUNT|ACTIVTRADES_LOGIN|MT5_LOGIN|"
    r"meta_api_token|account_id|account_token)", re.IGNORECASE
)
for f in sorted(hits.keys(), key=lambda k: -hits[k])[:10]:
    full = os.path.join(PROD_DIR, f)
    try:
        with open(full, "r", encoding="utf-8-sig", errors="ignore") as fp:
            src = fp.read()
    except Exception:
        continue
    matches = cred_pat.findall(src)
    if matches:
        print(f"  {f} : {set(matches)}")


# ----------------------------- 4 -----------------------------
banner("[4] Si position_sync.py existe, dump la structure (defs et imports)")
ps_candidates = [
    "position_sync.py",
    "metaapi_position_sync.py",
    "broker_position_sync.py",
]
for cand in ps_candidates:
    p = os.path.join(PROD_DIR, cand)
    if not os.path.exists(p):
        continue
    print(f"\n  --- {cand} ---")
    with open(p, "r", encoding="utf-8-sig") as f:
        src = f.read()
    print(f"  taille : {len(src):,} chars, {src.count(chr(10))+1} lignes")
    # imports
    print("  imports (top 15) :")
    for ln in src.split("\n")[:50]:
        if ln.startswith("import ") or ln.startswith("from "):
            print(f"    {ln}")
    # defs
    defs = re.findall(r"^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", src, re.MULTILINE)
    print(f"  fonctions ({len(defs)}) :")
    for name, args in defs:
        args_short = args.replace("\n", " ").replace("  ", " ")[:80]
        print(f"    {name}({args_short})")


# ----------------------------- 5 -----------------------------
banner("[5] .env / config files avec credentials")
for fname in [".env", "config.py", "config.json", "config.yaml",
              "credentials.json", "secrets.py", "settings.py"]:
    p = os.path.join(PROD_DIR, fname)
    if os.path.exists(p):
        sz = os.path.getsize(p)
        print(f"  {fname:30} present ({sz} bytes)")
        # Si .env, montre les CLES (pas les valeurs)
        if fname == ".env":
            with open(p, "r", encoding="utf-8-sig", errors="ignore") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln or ln.startswith("#"):
                        continue
                    if "=" in ln:
                        key = ln.split("=", 1)[0].strip()
                        if any(k in key.upper() for k in
                               ["META", "BROKER", "ACTIV", "MT5", "TOKEN", "API"]):
                            print(f"    {key} = ... (hidden)")


# ----------------------------- 6 -----------------------------
banner("[6] Recherche package python metaapi-cloud-sdk")
import subprocess
r = subprocess.run(
    [sys.executable, "-m", "pip", "show", "metaapi-cloud-sdk"],
    capture_output=True, text=True, timeout=15,
)
if r.returncode == 0:
    for ln in r.stdout.split("\n")[:5]:
        print(f"  {ln}")
else:
    print("  package metaapi-cloud-sdk NON installe")
    # Cherche d'autres SDK MT5 / metaapi
    for pkg in ["MetaTrader5", "MetaApi", "metaapi"]:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "show", pkg],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            print(f"  {pkg} installe :")
            for ln in r.stdout.split("\n")[:3]:
                print(f"    {ln}")

print()
print("[DONE]")
