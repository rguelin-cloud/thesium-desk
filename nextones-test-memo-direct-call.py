# -*- coding: utf-8 -*-
"""
Test direct : appelle generate_ic_memo() en Python (sans HTTP),
puis lit le memo cree et verifie la section Convergence Engine.

Bypass total de FastAPI / scheduler / cycle. On force un memo NOW.
"""
import os, sys, io, sqlite3, importlib, traceback, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")

# Ajoute le repo au path
if BASE not in sys.path:
    sys.path.insert(0, BASE)

# 1. Snapshot AVANT
print("=" * 60); print("1. SNAPSHOT AVANT"); print("=" * 60)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT MAX(id) as mx, COUNT(*) as c FROM ic_memos")
r = cur.fetchone()
id_before = r["mx"] or 0
count_before = r["c"] or 0
print(f"  max(id)={id_before}, count={count_before}")
conn.close()

# 2. Verifier que le patch est bien dans memo_generator.py
print("\n" + "=" * 60); print("2. VERIF PATCH EN PLACE"); print("=" * 60)
mg_path = os.path.join(BASE, "memo_generator.py")
with open(mg_path, "r", encoding="utf-8-sig") as f:
    mg_src = f.read()

markers = ["# [ICMEMO_CONVERGENCE_V1]", "_build_convergence_section", "## Convergence Engine"]
for mk in markers:
    n = mg_src.count(mk)
    print(f"  '{mk}' x{n}")
    if n == 0:
        print(f"    [WARN] marker absent !")

# 3. Importer le module et appeler generate_ic_memo
print("\n" + "=" * 60); print("3. APPEL DIRECT generate_ic_memo()"); print("=" * 60)
try:
    # Force reload au cas ou
    if "memo_generator" in sys.modules:
        del sys.modules["memo_generator"]
    import memo_generator
    print(f"  module charge depuis : {memo_generator.__file__}")
    print(f"  fonctions dispo : {[n for n in dir(memo_generator) if not n.startswith('_')][:20]}")

    # Inspection signature
    import inspect
    sig = inspect.signature(memo_generator.generate_ic_memo)
    print(f"  signature : generate_ic_memo{sig}")

    # Appel
    print("\n  Appel en cours...")
    result = memo_generator.generate_ic_memo()
    print(f"  result type: {type(result).__name__}")
    if isinstance(result, dict):
        print(f"  keys: {list(result.keys())}")
        for k, v in result.items():
            if isinstance(v, str) and len(v) > 200:
                print(f"    {k}: <str {len(v)} chars>")
            else:
                print(f"    {k}: {v!r}"[:200])
    elif isinstance(result, str):
        print(f"  markdown len: {len(result)}")
    else:
        print(f"  result: {result!r}"[:300])

except Exception as e:
    print(f"  [ERR] {type(e).__name__}: {e}")
    traceback.print_exc()

# 4. Snapshot APRES
print("\n" + "=" * 60); print("4. SNAPSHOT APRES"); print("=" * 60)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT MAX(id) as mx, COUNT(*) as c FROM ic_memos")
r = cur.fetchone()
id_after = r["mx"] or 0
count_after = r["c"] or 0
print(f"  max(id)={id_after}, count={count_after}")
print(f"  delta count = {count_after - count_before}")

# 5. Lire le memo le plus recent
print("\n" + "=" * 60); print("5. CONTENU DU DERNIER MEMO"); print("=" * 60)
cur.execute("SELECT id, date, title, full_markdown, created_at FROM ic_memos ORDER BY rowid DESC LIMIT 1")
last = cur.fetchone()
if last:
    print(f"  memo #{last['id']}  date={last['date']}  created={last['created_at']}")
    print(f"  title : {last['title']}")
    md = last['full_markdown'] or ""
    print(f"  markdown : {len(md)} chars")

    if "## Convergence Engine" in md:
        print("\n  [PASS] section 'Convergence Engine' presente")
        idx = md.find("## Convergence Engine")
        next_h = md.find("\n## ", idx + 5)
        section = md[idx:] if next_h == -1 else md[idx:next_h]
        print("\n  --- SECTION CONVERGENCE ---")
        print(section[:4000])
        print("  --- FIN ---")
    else:
        print("\n  [FAIL] section 'Convergence Engine' ABSENTE")
        print("  Headings trouves :")
        for m in re.finditer(r"^##\s+([^\n]+)", md, re.MULTILINE):
            print(f"    - {m.group(1)}")
else:
    print("  aucun memo")

conn.close()
print("\n[DONE]")
