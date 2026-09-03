# -*- coding: utf-8 -*-
# nextones-diag-8b2-which-replay-view-v1.py
# Determine quel replay_db_view.py est IMPORTE par replay_orchestrator
# (workspace vs prod dir vs autre) et compare son contenu au diag trace.

import os
import sys

# Reproduit l'env du smoke-test
os.environ["NEXTONES_REPLAY_MODE"] = "1"
PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
WORKSPACE = os.path.dirname(os.path.abspath(__file__))

if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

print("=" * 72)
print("DIAG 8B.2 - quel replay_db_view est importe ?")
print("=" * 72)

print(f"\nCWD               : {os.getcwd()}")
print(f"WORKSPACE script  : {WORKSPACE}")
print(f"PROD_DIR          : {PROD_DIR}")
print(f"\nsys.path (ordre d'import) :")
for i, p in enumerate(sys.path):
    print(f"  [{i:2d}] {p}")

import replay_db_view
print(f"\n--- replay_db_view ---")
print(f"  __file__  : {replay_db_view.__file__}")
print(f"  size      : {os.path.getsize(replay_db_view.__file__)} bytes")

# Compte les lignes
with open(replay_db_view.__file__, "r", encoding="utf-8-sig") as f:
    src = f.read()
n_lines = src.count("\n") + 1
print(f"  lines     : {n_lines}")

# Check signatures de fonctions
has_funcs = []
for name in ["open_replay_conn_at", "monkey_patch_for_replay", "restore_for_replay",
             "monkey_patch_freshness", "get_snapshot_stats"]:
    has = hasattr(replay_db_view, name)
    has_funcs.append((name, has))
    print(f"  has {name:<28s} : {has}")

# Check contenu critique : la liste static_tables doit contenir 'theses'
print(f"\n--- contenu fichier (extrait critique) ---")
needles = [
    'static_tables',
    'theses',
    'state_tables',
    'convergence_snapshots',
    'portfolio_state',
]
for n in needles:
    found = n in src
    print(f"  contient '{n}'  : {found}")

# Maintenant : importe replay_orchestrator et regarde QUEL replay_db_view il a importe
print(f"\n--- replay_orchestrator ---")
import replay_orchestrator
print(f"  __file__  : {replay_orchestrator.__file__}")
# Verifie la reference resolue
ref = replay_orchestrator.open_replay_conn_at
print(f"  open_replay_conn_at source : {ref.__module__}")
import importlib
mod_used = importlib.import_module(ref.__module__)
print(f"  module used        : {mod_used.__file__}")

# Test final : appelle open_replay_conn_at via replay_orchestrator's reference
# et compte tables produites
print(f"\n--- test direct via reference orchestrator ---")
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = replay_orchestrator.open_replay_conn_at("2026-06-10", DB_PATH)
rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print(f"  tables creees : {len(rows)}")
for r in rows:
    n = conn.execute(f"SELECT COUNT(*) FROM {r[0]}").fetchone()[0]
    print(f"    {r[0]:<32s} {n}")
conn.close()
