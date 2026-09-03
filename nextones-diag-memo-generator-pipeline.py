# -*- coding: utf-8 -*-
"""
Diag memo_generator.py et toute la chaine generation memo IC.
Objectif : identifier
  1. Fonctions publiques (genere memo, exporte PDF)
  2. Sources de donnees lues (theses, cycles, convergence ?)
  3. Format de sortie (markdown -> HTML -> PDF ? pdfkit/reportlab/weasyprint ?)
  4. Endpoints API qui declenchent la generation
  5. Point d'injection ideal pour section 'Verdict Convergence'
"""
import os, sys, re, io, sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")

# ---------------------------------------------------------------------------
# 1. memo_generator.py
# ---------------------------------------------------------------------------
mg_path = os.path.join(BASE, "memo_generator.py")
print("=" * 60)
print("1. memo_generator.py")
print("=" * 60)
if not os.path.isfile(mg_path):
    print(f"  [FAIL] introuvable : {mg_path}")
    sys.exit(0)

with open(mg_path, "r", encoding="utf-8-sig") as f:
    mg = f.read()
lines = mg.split("\n")
print(f"  {len(lines)} lignes, {len(mg)} chars")

# Imports
print("\n[IMPORTS]")
for i, line in enumerate(lines, 1):
    if line.startswith("import ") or line.startswith("from "):
        print(f"  L{i}: {line.strip()}")

# Fonctions
print("\n[FONCTIONS DEFINIES]")
for m in re.finditer(r'^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)', mg, re.MULTILINE):
    line_num = mg[:m.start()].count("\n") + 1
    print(f"  L{line_num}: def {m.group(1)}({m.group(2)[:80]})")

# Classes
print("\n[CLASSES]")
for m in re.finditer(r'^class\s+(\w+)', mg, re.MULTILINE):
    line_num = mg[:m.start()].count("\n") + 1
    print(f"  L{line_num}: class {m.group(1)}")

# Refs SQL / tables lues
print("\n[TABLES SQL REFERENCEES]")
sql_tables = set()
for m in re.finditer(r'(?:FROM|JOIN|UPDATE|INTO)\s+(\w+)', mg, re.IGNORECASE):
    sql_tables.add(m.group(1).lower())
for t in sorted(sql_tables):
    print(f"  {t}")

# diff_engine
print("\n[DIFF_ENGINE WIRING]")
for kw in ["diff_engine", "compute_cycle_diff", "Ce qui a changé", "Ce qui a chang", "J-1", "j_minus_1"]:
    for m in re.finditer(re.escape(kw), mg):
        line_num = mg[:m.start()].count("\n") + 1
        line = lines[line_num-1].strip()
        print(f"  L{line_num} ({kw}): {line[:160]}")
        break

# Convergence
print("\n[CONVERGENCE REFS (devrait etre vide pour confirmer le gap)]")
found_conv = False
for kw in ["convergence_snapshots", "sizing_multiplier", "forced_exit", "n_aligned"]:
    for m in re.finditer(re.escape(kw), mg):
        found_conv = True
        line_num = mg[:m.start()].count("\n") + 1
        line = lines[line_num-1].strip()
        print(f"  L{line_num} ({kw}): {line[:160]}")
        break
if not found_conv:
    print("  (vide - confirme que memo_generator ne lit pas convergence)")

# PDF / Markdown
print("\n[FORMAT SORTIE]")
for kw in ["pdfkit", "reportlab", "weasyprint", "fpdf", "markdown", "to_pdf", "render_pdf", "export_pdf", "html2pdf"]:
    cnt = mg.count(kw)
    if cnt:
        print(f"  '{kw}' : {cnt} occ")

# Structure attendue : cherche les sections existantes
print("\n[SECTIONS MEMO (titres H2/H3 ou ##)]")
for m in re.finditer(r'(##\s+[^\n]+|<h[23][^>]*>[^<]+</h[23]>)', mg):
    line_num = mg[:m.start()].count("\n") + 1
    print(f"  L{line_num}: {m.group(1)[:120]}")

# ---------------------------------------------------------------------------
# 2. Endpoint API memo
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("2. ENDPOINTS API memo")
print("=" * 60)

for fname in ["api_server.py", "api_server_with_static.py"]:
    p = os.path.join(BASE, fname)
    if not os.path.isfile(p):
        continue
    with open(p, "r", encoding="utf-8-sig") as f:
        c = f.read()
    cl = c.split("\n")
    print(f"\n  {fname}")
    for m in re.finditer(r'@app\.(get|post)\(\s*["\']([^"\']*memo[^"\']*)["\']', c, re.IGNORECASE):
        line_num = c[:m.start()].count("\n") + 1
        print(f"    L{line_num}: @app.{m.group(1)} {m.group(2)}")
    # endpoints qui appellent memo_generator
    for m in re.finditer(r'(memo_generator|generate_memo|render_memo|build_memo)\w*\(', c):
        line_num = c[:m.start()].count("\n") + 1
        print(f"    L{line_num} CALL: {cl[line_num-1].strip()[:160]}")

# ---------------------------------------------------------------------------
# 3. Table ic_memos
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("3. TABLE ic_memos")
print("=" * 60)
try:
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE name='ic_memos'")
    row = cur.fetchone()
    if row:
        print(row[0])
    else:
        print("  table introuvable")

    cur.execute("PRAGMA table_info(ic_memos)")
    print("\n  Colonnes :")
    for c in cur.fetchall():
        print(f"    {c[1]} ({c[2]})")

    cur.execute("SELECT COUNT(*) FROM ic_memos")
    print(f"\n  Total memos : {cur.fetchone()[0]}")

    cur.execute("SELECT id, ticker, created_at FROM ic_memos ORDER BY rowid DESC LIMIT 5")
    print("\n  5 plus recents :")
    for r in cur.fetchall():
        print(f"    #{r[0]}  {r[1]}  {r[2]}")

    # body sample
    cur.execute("SELECT id, ticker, body FROM ic_memos ORDER BY rowid DESC LIMIT 1")
    r = cur.fetchone()
    if r:
        body = r[2] or ""
        print(f"\n  Sample memo #{r[0]} {r[1]} - body ({len(body)} chars) :")
        print("  " + "-" * 58)
        for line in body.split("\n")[:30]:
            print("    " + line[:160])
        print("  " + "-" * 58)
    conn.close()
except Exception as e:
    print(f"  [ERREUR] {e}")

print("\n[DONE]")
