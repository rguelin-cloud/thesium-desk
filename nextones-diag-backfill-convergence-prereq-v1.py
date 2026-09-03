"""
DIAG pre-backfill convergence_snapshots historique.
Verifier si on peut RECONSTRUIRE convergence retro-actif sur 2026-03-14 -> 2026-06-08.

Questions cles :
A) Module convergence_engine : signature publique ?
B) Source agents historiques : a-t-on les outputs agents par cycle ?
C) Liste cycles eligibles dans la fenetre aveugle ?
D) Snapshot deja existant pour ces cycles (idempotence) ?
"""
import sqlite3
import os
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_FILE = os.path.join(DB, "thesium.db")
WINDOW_START = "20260314"
WINDOW_END = "20260608"

print("=" * 78)
print("[A] Module convergence_engine.py - localisation et signature")
print("=" * 78)

# Recherche du module convergence_engine
candidates = []
for root, dirs, files in os.walk(DB):
    # eviter venv et node_modules
    dirs[:] = [d for d in dirs if d not in ("venv", ".venv", "node_modules", "__pycache__", ".git")]
    for f in files:
        if f.startswith("convergence_engine") and f.endswith(".py"):
            full = os.path.join(root, f)
            candidates.append(full)

print("  Candidats trouves :", len(candidates))
for p in candidates:
    sz = os.path.getsize(p)
    print("    " + p + "  (" + str(sz) + " bytes)")

# Lire le premier candidat trouve et extraire signatures
if candidates:
    main_file = candidates[0]
    print("\n  Signatures publiques de", os.path.basename(main_file), ":")
    with open(main_file, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        s = line.rstrip()
        if s.startswith("def ") or s.startswith("class "):
            print("    L{:4d}: {}".format(i + 1, s[:120]))

print()
print("=" * 78)
print("[B] Tables d outputs agents historiques (pour reconstruire convergence)")
print("=" * 78)

con = sqlite3.connect(DB_FILE)
con.row_factory = sqlite3.Row
cur = con.cursor()

# Lister toutes les tables
tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall()]
print("  Total tables :", len(tables))

# Filtrer celles qui ressemblent a des outputs agents
agent_tables = [t for t in tables if any(k in t.lower() for k in
                ("agent", "thes", "convergence", "decision", "memo", "cycle"))]
print("\n  Tables candidates (agent/thesis/convergence/decision/memo/cycle) :")
for t in agent_tables:
    try:
        n = cur.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
    except sqlite3.Error:
        n = "ERR"
    print("    {:40s} n={}".format(t, n))

# Pour chaque table candidate, voir si elle a cycle_id et un sample en fenetre aveugle
print("\n  Pour chacune : a-t-elle cycle_id ? combien de rows en fenetre aveugle ?")
for t in agent_tables:
    try:
        cols = [r[1] for r in cur.execute("PRAGMA table_info(" + t + ")").fetchall()]
    except sqlite3.Error:
        continue
    has_cycle = any(c.lower() == "cycle_id" for c in cols)
    if has_cycle:
        try:
            n_window = cur.execute(
                "SELECT COUNT(*) FROM " + t +
                " WHERE substr(cycle_id,1,8) BETWEEN ? AND ?",
                (WINDOW_START, WINDOW_END)
            ).fetchone()[0]
        except sqlite3.Error as e:
            n_window = "ERR " + str(e)
        print("    {:40s} cols~={} n_in_window={}".format(t, len(cols), n_window))

print()
print("=" * 78)
print("[C] Cycles prod eligibles dans la fenetre aveugle 2026-03-14 -> 2026-06-08")
print("=" * 78)

# Distinct cycles a partir de regime_log (suppose qu'il y a 1 cycle = 1 entry)
rows = cur.execute(
    "SELECT substr(cycle_id,1,8) day_t, COUNT(DISTINCT cycle_id) n_cycles "
    "FROM regime_log "
    "WHERE substr(cycle_id,1,8) BETWEEN ? AND ? "
    "GROUP BY substr(cycle_id,1,8) "
    "ORDER BY day_t",
    (WINDOW_START, WINDOW_END)
).fetchall()
total_cycles = sum(r["n_cycles"] for r in rows)
print("  Jours avec cycles :", len(rows))
print("  Total cycles dans fenetre aveugle :", total_cycles)
print("\n  Sample 10 premiers jours :")
for r in rows[:10]:
    print("    {} : {} cycles".format(r["day_t"], r["n_cycles"]))
print("  ...")
print("  Sample 10 derniers jours :")
for r in rows[-10:]:
    print("    {} : {} cycles".format(r["day_t"], r["n_cycles"]))

print()
print("=" * 78)
print("[D] Snapshots convergence deja existants (idempotence)")
print("=" * 78)
rows = cur.execute(
    "SELECT substr(cycle_id,1,8) day_t, COUNT(*) n "
    "FROM convergence_snapshots "
    "WHERE substr(cycle_id,1,8) BETWEEN ? AND ? "
    "GROUP BY substr(cycle_id,1,8) "
    "ORDER BY day_t",
    (WINDOW_START, WINDOW_END)
).fetchall()
print("  Snapshots existants dans la fenetre aveugle :", len(rows), "jours")
for r in rows:
    print("    {} : {} snapshots".format(r["day_t"], r["n"]))

# Verifier aussi 'theses' qui semble etre la table cle pour les decisions agents
print()
print("=" * 78)
print("[E] Table 'theses' - structure et coverage fenetre aveugle")
print("=" * 78)
try:
    cols = [r[1] for r in cur.execute("PRAGMA table_info(theses)").fetchall()]
    print("  cols=", cols)
    n_total = cur.execute("SELECT COUNT(*) FROM theses").fetchone()[0]
    print("  total rows :", n_total)
    if "cycle_id" in cols:
        n_window = cur.execute(
            "SELECT COUNT(*) FROM theses "
            "WHERE substr(cycle_id,1,8) BETWEEN ? AND ?",
            (WINDOW_START, WINDOW_END)
        ).fetchone()[0]
        print("  rows en fenetre aveugle :", n_window)
        # Distinct agents / sources
        try:
            rows = cur.execute(
                "SELECT DISTINCT agent_id, source FROM theses LIMIT 20"
            ).fetchall()
            print("  sample agents/sources :")
            for r in rows:
                print("    ", dict(r))
        except sqlite3.Error as e:
            print("  [INFO]", e)
except sqlite3.Error as e:
    print("  [ERR]", e)

con.close()
print()
print("=" * 78)
print("DONE - diag pre-backfill convergence")
print("=" * 78)
