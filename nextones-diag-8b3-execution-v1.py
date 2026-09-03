# -*- coding: utf-8 -*-
# nextones-diag-8b3-execution-v1.py
# Cartographie Jalon 8B.3 : risk_pretrade + fill_simulator + tables execution
#
# Recupere :
#   - Modules risk_pretrade / fill_simulator presents + paths + tailles
#   - Signatures (fonctions top-level, parametres, defauts)
#   - Imports principaux + dependances DB (conn vs db_path)
#   - DDL exact prod : orders, fills, portfolio_positions, portfolio_history
#   - Indexes associes
#   - Echantillon de donnees prod (1-2 lignes par table) pour comprendre les formats
#
# Mode strict lecture-seule. Aucune ecriture.

import os
import sys
import sqlite3
import ast
import inspect
from datetime import datetime

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)


def sep(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def dump_module_signatures(module_name):
    """Liste les fonctions/classes top-level d'un module + signatures."""
    sep(f"MODULE : {module_name}")
    try:
        mod = __import__(module_name)
    except Exception as e:
        print(f"  [ERR] import: {e}")
        return

    path = getattr(mod, "__file__", None)
    print(f"  __file__ : {path}")
    if path and os.path.exists(path):
        sz = os.path.getsize(path)
        print(f"  size     : {sz} bytes")

    # Parse AST pour fonctions/classes top-level + signatures
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                src = f.read()
            tree = ast.parse(src)
            print(f"  --- TOP-LEVEL FUNCTIONS ---")
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    args = []
                    for a in node.args.args:
                        args.append(a.arg)
                    defaults_count = len(node.args.defaults)
                    arg_str = ", ".join(args)
                    print(f"    def {node.name}({arg_str})   [defaults={defaults_count}]")
                elif isinstance(node, ast.ClassDef):
                    print(f"    class {node.name}")
                    for sub in node.body:
                        if isinstance(sub, ast.FunctionDef):
                            args = [a.arg for a in sub.args.args]
                            print(f"        def {sub.name}({', '.join(args)})")

            # Imports
            print(f"  --- IMPORTS ---")
            for node in tree.body[:30]:
                if isinstance(node, ast.Import):
                    for n in node.names:
                        print(f"    import {n.name}")
                elif isinstance(node, ast.ImportFrom):
                    names = ", ".join(n.name for n in node.names)
                    print(f"    from {node.module} import {names}")
        except Exception as e:
            print(f"  [ERR] AST: {e}")


def dump_table_ddl(conn, tname):
    sep(f"TABLE prod : {tname}")
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tname,)
    ).fetchone()
    if not row:
        print(f"  [ABSENT]")
        return False
    print("  CREATE TABLE :")
    print("    " + (row[0] or "").replace("\n", "\n    "))

    # Indexes
    idx = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (tname,),
    ).fetchall()
    if idx:
        print("  INDEXES :")
        for name, sql in idx:
            print(f"    {name} : {sql}")

    # Count
    try:
        n = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
        print(f"  ROW COUNT : {n}")
    except Exception as e:
        print(f"  [ERR count] {e}")

    # Echantillon 2 lignes
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({tname})").fetchall()]
        print(f"  COLUMNS   : {cols}")
        rows = conn.execute(f"SELECT * FROM {tname} ORDER BY rowid DESC LIMIT 2").fetchall()
        if rows:
            print("  SAMPLE (2 lignes recentes) :")
            for r in rows:
                d = dict(zip(cols, r))
                print(f"    {d}")
    except Exception as e:
        print(f"  [ERR sample] {e}")

    return True


def find_files_by_pattern(root, patterns):
    """Cherche des fichiers .py contenant un pattern dans leur nom."""
    sep(f"RECHERCHE FICHIERS : {patterns}")
    hits = []
    for fname in sorted(os.listdir(root)):
        low = fname.lower()
        if any(p in low for p in patterns) and low.endswith(".py"):
            full = os.path.join(root, fname)
            sz = os.path.getsize(full)
            hits.append((fname, sz))
    for f, s in hits:
        print(f"  {f}  ({s} bytes)")
    return hits


def search_pattern_in_files(root, pattern, max_files=50):
    """Cherche un identifiant dans les .py prod."""
    sep(f"RECHERCHE pattern '{pattern}' dans .py")
    hits = []
    files = [f for f in os.listdir(root) if f.endswith(".py")]
    for fname in sorted(files)[:200]:
        full = os.path.join(root, fname)
        try:
            with open(full, "r", encoding="utf-8-sig", errors="ignore") as f:
                src = f.read()
            if pattern in src:
                lines = [(i, l.strip()) for i, l in enumerate(src.splitlines(), 1) if pattern in l]
                hits.append((fname, lines[:3]))
        except Exception:
            pass
    for fname, lines in hits[:15]:
        print(f"  {fname}:")
        for ln, l in lines:
            print(f"    L{ln}: {l[:140]}")
    print(f"  Total fichiers avec '{pattern}' : {len(hits)}")
    return hits


def main():
    print(f"DIAG 8B.3 - {datetime.now()}")
    print(f"PROD_DIR : {PROD_DIR}")
    print(f"DB_PATH  : {DB_PATH}")

    # 1. Fichiers candidats
    find_files_by_pattern(PROD_DIR, ["risk_pretrade", "fill_simulator", "execution_engine"])

    # 2. Modules signatures
    for mod in ["risk_pretrade", "fill_simulator", "execution_engine"]:
        dump_module_signatures(mod)

    # 3. Tables prod DDL
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    for t in ["orders", "fills", "portfolio_positions", "portfolio_state",
              "portfolio_history", "instruments"]:
        dump_table_ddl(conn, t)

    # 4. Variantes risk_pretrade (v1 / v2 / etc)
    search_pattern_in_files(PROD_DIR, "def risk_check_order")
    search_pattern_in_files(PROD_DIR, "def risk_pretrade")
    search_pattern_in_files(PROD_DIR, "def simulate_fill")
    search_pattern_in_files(PROD_DIR, "def fill_order")
    search_pattern_in_files(PROD_DIR, "def execute_order")
    search_pattern_in_files(PROD_DIR, "def create_and_execute_order")

    # 5. Comment l'execution wire-t-elle ces modules ?
    search_pattern_in_files(PROD_DIR, "from risk_pretrade")
    search_pattern_in_files(PROD_DIR, "from fill_simulator")

    conn.close()
    print()
    print("=" * 72)
    print("DIAG 8B.3 termine.")
    print("=" * 72)


if __name__ == "__main__":
    main()
