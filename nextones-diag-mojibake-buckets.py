# -*- coding: utf-8 -*-
"""
Diagnostic du double-encoding sur buckets_json.

Strategie :
1. Lire convergence_snapshot (cycle 20260609-091332) en DB brut bytes
2. Voir comment les drivers sont stockes (≤ vs â‰¤)
3. Tracer la chaine : insertion -> read -> json.loads -> rendu markdown
4. Identifier le point ou le double-encoding se produit
"""
import os, sys, io, sqlite3, json, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")

print("=" * 60); print("1. SCHEMA convergence_snapshot"); print("=" * 60)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# tables candidates
for t in ("convergence_snapshot", "convergence_snapshots", "cycle_convergence"):
    try:
        cur.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{t}'")
        r = cur.fetchone()
        if r:
            print(f"  Table {t} : OK")
            print(f"    {r['sql']}")
            target_table = t
    except Exception as e:
        pass

# Lister toutes les tables avec 'convergence' dans le nom
print("\n  Toutes tables convergence* :")
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name LIKE '%convergence%'")
for r in cur.fetchall():
    print(f"    - {r['name']}")
    print(f"      {r['sql'][:300]}")

print("\n" + "=" * 60); print("2. DERNIER SNAPSHOT - bytes bruts"); print("=" * 60)
# Trouve la bonne table
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%convergence%'")
tables = [r["name"] for r in cur.fetchall()]
print(f"  Tables trouvees : {tables}")

for tbl in tables:
    cur.execute(f"PRAGMA table_info({tbl})")
    cols = [r["name"] for r in cur.fetchall()]
    print(f"\n  Table {tbl} cols : {cols}")
    # cherche une colonne JSON/buckets
    json_cols = [c for c in cols if "json" in c.lower() or "bucket" in c.lower() or "data" in c.lower() or "snapshot" in c.lower()]
    if json_cols:
        for jc in json_cols:
            try:
                cur.execute(f"SELECT {jc} FROM {tbl} ORDER BY rowid DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    val = row[jc]
                    if val:
                        print(f"\n  --- Colonne {jc} (last row) ---")
                        if isinstance(val, bytes):
                            print(f"    Type: bytes ({len(val)} octets)")
                            # Chercher patterns mojibake
                            for needle in (b"\xe2\x89\xa4", b"\xe2\x86\x92", b"\xc3\xa2\xe2\x80\xb0\xc2\xa4", b"\xc3\xa2\xe2\x80\xa0\xe2\x80\x99"):
                                cnt = val.count(needle)
                                if cnt:
                                    print(f"    pattern {needle!r} x{cnt}")
                            # Decodage essai
                            try:
                                s = val.decode("utf-8")
                                # Chercher mojibake patterns en string
                                for s_needle in ("≤", "→", "â‰¤", "â†'", "â†’", "â‰¥"):
                                    n = s.count(s_needle)
                                    if n:
                                        print(f"    str pattern '{s_needle}' x{n}")
                            except Exception as e:
                                print(f"    decode utf-8 fail: {e}")
                        elif isinstance(val, str):
                            print(f"    Type: str ({len(val)} chars)")
                            # bytes raw du str
                            raw = val.encode("utf-8", errors="replace")
                            for s_needle in ("≤", "→", "â‰¤", "â†'", "â†™", "â‰¥"):
                                n = val.count(s_needle)
                                if n:
                                    print(f"    pattern '{s_needle}' x{n}")
                            # Echantillon
                            print(f"    sample (300c): {val[:300]}")
            except Exception as e:
                print(f"    [ERR] read {jc}: {e}")

print("\n" + "=" * 60); print("3. CONTEXTE INSERTION - cherche ou buckets_json est ecrit"); print("=" * 60)
# Cherche les INSERT INTO convergence_*
import glob
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in (".venv", "venv", "__pycache__", ".git", "node_modules") and not d.startswith("_backups")]
    for f in files:
        if not f.endswith(".py"):
            continue
        fp = os.path.join(root, f)
        try:
            with open(fp, "r", encoding="utf-8-sig") as fh:
                src = fh.read()
        except Exception:
            continue
        for m in re.finditer(r"(INSERT\s+(?:OR\s+\w+\s+)?INTO\s+convergence_\w+|UPDATE\s+convergence_\w+)", src, re.IGNORECASE):
            line_num = src[:m.start()].count("\n") + 1
            rel = os.path.relpath(fp, BASE)
            print(f"  {rel}:L{line_num}  {m.group(0)}")
        # Cherche json.dumps autour de bucket/convergence
        for m in re.finditer(r"json\.dumps\([^)]+\)", src):
            line_num = src[:m.start()].count("\n") + 1
            # contexte 2 lignes avant
            start_ctx = max(0, src.rfind("\n", 0, m.start() - 150))
            ctx = src[start_ctx:m.start()].lower()
            if "bucket" in ctx or "convergence" in ctx or "driver" in ctx:
                rel = os.path.relpath(fp, BASE)
                print(f"  {rel}:L{line_num}  json.dumps (contexte bucket/convergence)")

conn.close()
print("\n[DONE]")
