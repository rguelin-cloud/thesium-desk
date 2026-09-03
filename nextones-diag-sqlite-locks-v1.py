# -*- coding: utf-8 -*-
"""
Diag complet : ou ouvre-t-on des connexions SQLite ? Lesquelles ont busy_timeout ?

1. Scan tous les .py prod (sans _backups) pour :
   - sqlite3.connect(
   - get_db()
   - PRAGMA busy_timeout
   - PRAGMA journal_mode
2. Identifie les helpers centralises s'ils existent
3. Repere les ouvertures "nues" (sans timeout)
4. Cartographie les agents qui ont crashe (BTC/ETH/HYPE/LINK/SOL/ZEC)
"""
import os, sys, io, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Collecte des .py prod (skip backups, venv, cache)
py_files = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith("_backups") and d not in (".venv", "venv", "__pycache__", ".git", "node_modules")]
    for f in files:
        if f.endswith(".py") and not f.startswith("nextones-"):
            py_files.append(os.path.join(root, f))

print(f"Scan {len(py_files)} fichiers prod (hors backups, hors patches nextones-*)")

# 1. Helpers centralises ?
print("\n" + "=" * 70); print("1. HELPERS CENTRALISES"); print("=" * 70)
helpers = []
for fp in py_files:
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:
        continue
    # Cherche des fonctions get_db, get_connection, open_db, _open_db
    for m in re.finditer(r'^def\s+(get_db|get_connection|open_db|_open_db\w*|connect_db)\s*\(', src, re.MULTILINE):
        line = src[:m.start()].count("\n") + 1
        rel = os.path.relpath(fp, BASE)
        # Capture les 25 lignes suivantes pour voir si PRAGMA
        lines = src.split("\n")
        body = "\n".join(lines[line-1:line+25])
        has_busy = "busy_timeout" in body.lower()
        has_wal = "journal_mode" in body.lower() and "wal" in body.lower()
        helpers.append((rel, line, m.group(1), has_busy, has_wal))
        print(f"  {rel}:L{line} def {m.group(1)}()  busy_timeout={has_busy}  WAL={has_wal}")

# 2. Toutes les ouvertures sqlite3.connect()
print("\n" + "=" * 70); print("2. sqlite3.connect() DIRECTS"); print("=" * 70)
direct_connects = []
for fp in py_files:
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:
        continue
    if "sqlite3.connect" not in src:
        continue
    lines = src.split("\n")
    for m in re.finditer(r"sqlite3\.connect\s*\(", src):
        line_num = src[:m.start()].count("\n") + 1
        line = lines[line_num - 1].strip()
        # Skip si dans un commentaire
        if line.startswith("#"):
            continue
        rel = os.path.relpath(fp, BASE)
        # Verifie si busy_timeout est setup dans les 15 lignes suivantes
        context = "\n".join(lines[line_num-1:line_num+15])
        has_timeout = "busy_timeout" in context.lower()
        direct_connects.append((rel, line_num, line[:120], has_timeout))

# Tri : ceux SANS timeout en premier
direct_connects.sort(key=lambda x: (x[3], x[0], x[1]))
print(f"  {len(direct_connects)} sqlite3.connect() trouve(s)")
print(f"\n  --- SANS busy_timeout (DANGEREUX) ---")
n_dangerous = 0
for rel, ln, line, ht in direct_connects:
    if not ht:
        n_dangerous += 1
        print(f"  {rel}:L{ln}  {line}")
print(f"\n  Total dangereux : {n_dangerous}")

print(f"\n  --- AVEC busy_timeout (OK) ---")
for rel, ln, line, ht in direct_connects:
    if ht:
        print(f"  {rel}:L{ln}  {line}")

# 3. Fichiers des agents crashes (BTC/ETH/HYPE/LINK/SOL/ZEC)
print("\n" + "=" * 70); print("3. AGENTS CRYPTO CRASHES - CryptoAgent connection points"); print("=" * 70)
candidates = ["pplx_crypto_agent.py", "crypto_agent.py", "scheduler.py", "agents.py", "data_ingestion.py", "pplx_client.py"]
for fn in candidates:
    fp = os.path.join(BASE, fn)
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")
    # Cherche sqlite3.connect dans ces fichiers
    for m in re.finditer(r"sqlite3\.connect\s*\(", src):
        line_num = src[:m.start()].count("\n") + 1
        line = lines[line_num - 1].strip()
        if line.startswith("#"):
            continue
        # Contexte 2 lignes avant
        ctx_before = " | ".join(l.strip() for l in lines[max(0, line_num-3):line_num-1] if l.strip())
        context = "\n".join(lines[line_num-1:line_num+10])
        has_timeout = "busy_timeout" in context.lower()
        print(f"\n  {fn}:L{line_num}  busy_timeout={has_timeout}")
        print(f"    ctx_before: {ctx_before[:100]}")
        print(f"    line     : {line[:140]}")

# 4. Scheduler price refresh path
print("\n" + "=" * 70); print("4. SCHEDULER PRICE REFRESH PATH"); print("=" * 70)
for fn in ("scheduler.py", "data_ingestion.py", "data_macro.py"):
    fp = os.path.join(BASE, fn)
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")
    # Cherche les fonctions de refresh
    for m in re.finditer(r'^(\s*)(?:async\s+)?def\s+(refresh_\w+|update_\w+|_refresh\w*|\w*_price\w*)\s*\(', src, re.MULTILINE):
        line_num = src[:m.start()].count("\n") + 1
        name = m.group(2)
        # Verifie si la fonction utilise sqlite3.connect
        # On regarde les 100 lignes suivantes
        body = "\n".join(lines[line_num-1:line_num+100])
        if "sqlite3.connect" in body or ("conn" in body and "execute" in body):
            uses_helper = re.search(r'\b(get_db|get_connection|open_db|_open_db)\s*\(', body)
            print(f"  {fn}:L{line_num} def {name}()  uses_helper={bool(uses_helper)}")

# 5. PRAGMA WAL deja en place quelque part ?
print("\n" + "=" * 70); print("5. PRAGMA WAL DEJA APPLIQUE ?"); print("=" * 70)
for fp in py_files:
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:
        continue
    if "journal_mode" not in src.lower():
        continue
    lines = src.split("\n")
    for m in re.finditer(r"(?i)journal_mode\s*=?\s*wal", src):
        line_num = src[:m.start()].count("\n") + 1
        line = lines[line_num - 1].strip()
        if line.startswith("#"):
            continue
        rel = os.path.relpath(fp, BASE)
        print(f"  {rel}:L{line_num}  {line[:140]}")

print("\n[DONE]")
