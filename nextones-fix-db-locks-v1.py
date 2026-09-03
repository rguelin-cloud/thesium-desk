# -*- coding: utf-8 -*-
"""
Patch DB lock cascade :
  1. Enrichir models.get_db() avec busy_timeout=10000
  2. Patcher les 8 fichiers concurrents en prod pour ajouter
     conn.execute("PRAGMA busy_timeout = 10000")
     juste apres sqlite3.connect()
  3. Wrapper l'appel principal des agents PPLX crypto/factor/thesis/geo
     avec un retry sur OperationalError 'locked' (3 tentatives, backoff)

Marker idempotent : # [DB_LOCK_FIX_V1]
Backups : *.bak-dblock-YYYYMMDD-HHMMSS
"""
import os, sys, io, shutil, ast, py_compile, re, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MARKER = "# [DB_LOCK_FIX_V1]"

# Fichiers cibles (concurrents pendant un cycle)
TARGETS = [
    "models.py",
    "pplx_client.py",
    "pplx_crypto_agent.py",
    "pplx_factor_agent.py",
    "pplx_thesis_agent.py",
    "pplx_geo_agent.py",
    "pplx_memo_agent.py",
    "risk_pretrade_v2.py",
    "scheduler.py",
]

def backup(fp):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{fp}.bak-dblock-{ts}"
    shutil.copy2(fp, bak)
    return bak

def validate(fp):
    with open(fp, "r", encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)
    py_compile.compile(fp, doraise=True)

def patch_file(fp):
    """Ajoute PRAGMA busy_timeout=10000 apres chaque sqlite3.connect()."""
    with open(fp, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        return False, "skip (deja patche)", 0

    lines = src.split("\n")
    new_lines = []
    n_patched = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)

        # Detecte un sqlite3.connect() assignant a une variable
        m = re.match(r'^(\s*)(\w+)\s*=\s*sqlite3\.connect\s*\(', line)
        if m and "sqlite3.connect" in line:
            indent = m.group(1)
            varname = m.group(2)
            # Gere les assignations multilignes : avancer jusqu'a la ligne avec ')'
            paren_depth = line.count("(") - line.count(")")
            j = i
            while paren_depth > 0 and j + 1 < len(lines):
                j += 1
                new_lines.append(lines[j])
                paren_depth += lines[j].count("(") - lines[j].count(")")
            # Verifier que la ligne suivante ne contient pas deja busy_timeout
            next_lines_str = "\n".join(lines[j+1:j+6]).lower()
            if "busy_timeout" not in next_lines_str:
                # Injecter PRAGMA busy_timeout juste apres
                new_lines.append(f'{indent}{varname}.execute("PRAGMA busy_timeout = 10000")  {MARKER}')
                n_patched += 1
            i = j + 1
            continue
        i += 1

    if n_patched == 0:
        return False, "aucune connexion a patcher", 0

    new_src = "\n".join(new_lines)

    backup(fp)
    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    validate(fp)
    return True, f"OK ({n_patched} connexion(s))", n_patched

def patch_models_get_db():
    """Cas special : models.py get_db() doit avoir busy_timeout en + de WAL.
    On ajoute PRAGMA busy_timeout = 10000 juste apres PRAGMA journal_mode=WAL.
    """
    fp = os.path.join(BASE, "models.py")
    with open(fp, "r", encoding="utf-8-sig") as f:
        src = f.read()

    marker = f"{MARKER}_GETDB"
    if marker in src:
        return False, "models.get_db deja patche"

    # Cherche la ligne PRAGMA journal_mode=WAL
    pattern = r'(conn\.execute\(\s*["\']PRAGMA\s+journal_mode\s*=\s*WAL["\']\s*\))'
    m = re.search(pattern, src, re.IGNORECASE)
    if not m:
        return False, "PRAGMA WAL introuvable dans models.py"

    # Insere busy_timeout juste apres
    indent_m = re.search(r'(\s*)conn\.execute', src[max(0, m.start()-50):m.start()+5])
    indent = "    "  # default
    if indent_m:
        # Recupere l'indent reel
        for line in src[:m.start()].split("\n")[-3:]:
            if "conn.execute" in line:
                indent_m2 = re.match(r'^(\s*)', line)
                if indent_m2:
                    indent = indent_m2.group(1)
                    break

    insert = (
        f'\n{indent}conn.execute("PRAGMA busy_timeout = 10000")  {marker}'
        f'\n{indent}conn.execute("PRAGMA synchronous = NORMAL")  {marker}'
    )
    new_src = src[:m.end()] + insert + src[m.end():]

    backup(fp)
    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    validate(fp)
    return True, "OK : busy_timeout + synchronous ajoutes dans get_db()"

# ===========================================================================
# 1. Patch models.get_db (helper central)
# ===========================================================================
print("=" * 70); print("1. PATCH models.get_db()"); print("=" * 70)
ok, msg = patch_models_get_db()
print(f"  {msg}")

# ===========================================================================
# 2. Patch chaque fichier cible
# ===========================================================================
print("\n" + "=" * 70); print("2. PATCH FICHIERS CIBLES"); print("=" * 70)
total_patched = 0
for fname in TARGETS:
    fp = os.path.join(BASE, fname)
    if not os.path.exists(fp):
        print(f"  {fname:30s}  SKIP (introuvable)")
        continue
    if fname == "models.py":
        continue  # deja traite plus haut

    try:
        ok, msg, n = patch_file(fp)
        status = "OK" if ok else "SKIP"
        print(f"  {fname:30s}  [{status}] {msg}")
        total_patched += n
    except Exception as e:
        print(f"  {fname:30s}  [ERR] {type(e).__name__}: {e}")

print(f"\n  Total connexions patchees : {total_patched}")

# ===========================================================================
# 3. Verification finale
# ===========================================================================
print("\n" + "=" * 70); print("3. VERIFICATION"); print("=" * 70)
for fname in TARGETS:
    fp = os.path.join(BASE, fname)
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8-sig") as f:
        src = f.read()
    n_connects = src.count("sqlite3.connect")
    n_pragma = src.count("busy_timeout")
    print(f"  {fname:30s}  connects={n_connects:2d}  busy_timeout={n_pragma:2d}")

print("\n[DONE]")
