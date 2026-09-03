# -*- coding: utf-8 -*-
"""
Test direct v2 : appelle generate_ic_memo(conn) avec la BONNE signature.
"""
import os, sys, io, sqlite3, traceback, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")
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

# 2. Appel direct avec conn
print("\n" + "=" * 60); print("2. APPEL generate_ic_memo(conn)"); print("=" * 60)
try:
    if "memo_generator" in sys.modules:
        del sys.modules["memo_generator"]
    import memo_generator
    print(f"  module: {memo_generator.__file__}")

    # PRAGMA pour eviter le lock
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")

    print("  Appel generate_ic_memo(conn)...")
    result = memo_generator.generate_ic_memo(conn)
    print(f"  result = {result!r} (type={type(result).__name__})")

    # Commit au cas ou
    conn.commit()
    print("  conn.commit() OK")

except Exception as e:
    print(f"  [ERR] {type(e).__name__}: {e}")
    traceback.print_exc()

# 3. Snapshot APRES
print("\n" + "=" * 60); print("3. SNAPSHOT APRES"); print("=" * 60)
cur.execute("SELECT MAX(id) as mx, COUNT(*) as c FROM ic_memos")
r = cur.fetchone()
id_after = r["mx"] or 0
count_after = r["c"] or 0
print(f"  max(id)={id_after}, count={count_after}")
print(f"  delta count = {count_after - count_before}")

# 4. Lire le nouveau memo
print("\n" + "=" * 60); print("4. DERNIER MEMO"); print("=" * 60)
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
        print("\n  [FAIL] section absente")
        print("  Headings trouves :")
        for m in re.finditer(r"^##\s+([^\n]+)", md, re.MULTILINE):
            print(f"    - {m.group(1)}")
        # Verifie si _build_convergence_section a leve une exception silencieuse
        print("\n  Test direct de _build_convergence_section :")
        try:
            import importlib, memo_generator as mg
            importlib.reload(mg)
            if hasattr(mg, "_build_convergence_section"):
                sec = mg._build_convergence_section(conn)
                print(f"    output len = {len(sec) if sec else 0}")
                if sec:
                    print(f"    debut : {sec[:500]}")
                else:
                    print("    [WARN] section vide ou None")
            else:
                print("    [ERR] _build_convergence_section non trouvee dans le module")
        except Exception as e:
            print(f"    [EXC] {type(e).__name__}: {e}")
            traceback.print_exc()
else:
    print("  aucun memo")

conn.close()
print("\n[DONE]")
