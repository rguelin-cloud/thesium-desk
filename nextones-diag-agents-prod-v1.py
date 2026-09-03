# -*- coding: utf-8 -*-
# nextones-diag-agents-prod-v1.py
# Pre-jalon 8B.1 : inspection des 8 agents quant pour decider du pattern wrapper
#
# Pour chaque agent :
#  - localisation du fichier .py
#  - signature des fonctions/classes principales
#  - acces DB (sqlite3.connect calls + ecritures INSERT/UPDATE)
#  - dependance market_regime_v1 / convergence_engine

import os
import re
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

AGENTS = [
    ("market_regime_v1",          ["market_regime_v1.py"]),
    ("factor_agent",              ["pplx_factor_agent.py", "factor_agent.py"]),
    ("micro_agent",               ["micro_agent.py", "agents/micro_agent.py"]),
    ("crypto_agent",              ["pplx_crypto_agent.py", "crypto_agent.py"]),
    ("exit_driver",               ["exit_driver.py", "exit_agent.py"]),
    ("convergence_engine",        ["convergence_engine.py"]),
    ("portfolio_construction",    ["portfolio_construction_agent.py"]),
    ("risk_pretrade_v2",          ["risk_pretrade.py", "risk_pretrade_v2.py", "risk_engine.py"]),
]


def find_first(candidates):
    for c in candidates:
        p = os.path.join(ROOT, c)
        if os.path.exists(p):
            return p
    return None


def scan_file(path):
    """Retourne dict avec statistiques sur les acces DB."""
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            src = f.read()
    except Exception as e:
        return {"error": str(e)}

    lines = src.splitlines()
    n = len(lines)

    # Defs / classes
    defs = re.findall(r"^def\s+(\w+)\s*\(([^)]*)\)", src, re.MULTILINE)
    classes = re.findall(r"^class\s+(\w+)", src, re.MULTILINE)

    # sqlite3 access
    connects = len(re.findall(r"sqlite3\.connect\s*\(", src))
    inserts = len(re.findall(r"\bINSERT\s+INTO\b", src, re.IGNORECASE))
    updates = len(re.findall(r"\bUPDATE\s+\w+\s+SET\b", src, re.IGNORECASE))
    deletes = len(re.findall(r"\bDELETE\s+FROM\b", src, re.IGNORECASE))
    selects = len(re.findall(r"\bSELECT\b", src, re.IGNORECASE))

    # Imports inter-agents
    imports = re.findall(r"^(?:from|import)\s+([\w_.]+)", src, re.MULTILINE)
    relevant_imports = [i for i in imports if any(k in i for k in
                        ["market_regime", "convergence", "factor", "micro", "crypto",
                         "exit_", "portfolio_construction", "risk_pretrade",
                         "replay_adapters", "fill_simulator"])]

    # Detection acces DB prod (chemins/vars suspects)
    db_path_hits = re.findall(r'thesium\.db|THESIUM_DB|DB_PATH', src, re.IGNORECASE)

    # 2 premieres signatures de fonctions "interessantes" (run / detect / build / score / generate / execute)
    interesting = []
    for fname, fargs in defs:
        if re.match(r"^(run|detect|build|score|generate|execute|compute|propose|evaluate|check|apply|process)", fname):
            interesting.append((fname, fargs))

    return {
        "path": path,
        "lines": n,
        "defs": len(defs),
        "classes": classes,
        "sqlite_connects": connects,
        "selects": selects,
        "inserts": inserts,
        "updates": updates,
        "deletes": deletes,
        "imports_inter": relevant_imports,
        "db_path_hits": len(db_path_hits),
        "interesting_defs": interesting[:6],
    }


def main():
    print("=" * 80)
    print("DIAG AGENTS PROD - pre-jalon 8B.1")
    print("=" * 80)
    print(f"ROOT: {ROOT}")
    print()

    for agent_name, candidates in AGENTS:
        path = find_first(candidates)
        print("-" * 80)
        print(f"AGENT : {agent_name}")
        if path is None:
            print(f"  [!!] FICHIER INTROUVABLE parmi : {candidates}")
            continue
        info = scan_file(path)
        if "error" in info:
            print(f"  [ERR] {info['error']}")
            continue
        rel = os.path.relpath(path, ROOT)
        print(f"  fichier        : {rel}")
        print(f"  lignes         : {info['lines']}")
        print(f"  classes        : {info['classes']}")
        print(f"  defs total     : {info['defs']}")
        print(f"  sqlite connect : {info['sqlite_connects']}")
        print(f"  SELECT         : {info['selects']}")
        print(f"  INSERT/UPDATE/DELETE : {info['inserts']}/{info['updates']}/{info['deletes']}")
        print(f"  DB_PATH refs   : {info['db_path_hits']}")
        if info["imports_inter"]:
            print(f"  imports inter  : {info['imports_inter']}")
        if info["interesting_defs"]:
            print(f"  fonctions cles :")
            for n, a in info["interesting_defs"]:
                a_short = a if len(a) <= 80 else a[:77] + "..."
                print(f"    def {n}({a_short})")
        print()

    print("=" * 80)
    print("ANALYSE WRAPPER PATTERN")
    print("=" * 80)
    print("""
Pour chaque agent, le wrapper replay() doit :
  1. Accepter (day_t, adapters_dict, run_id) au lieu de la lecture DB prod
  2. Reutiliser la logique de calcul (algorithmes inchanges)
  3. NE PAS appeler sqlite3.connect(thesium.db) directement
  4. NE PAS faire d'INSERT/UPDATE dans les tables prod
  5. Ecrire UNIQUEMENT dans les tables replay_* via l'orchestrator

Criteres d'eligibilite Voie A par agent :
  - peu d'INSERT/UPDATE : facile a wrapper
  - beaucoup d'ecritures : risque eleve, fallback voie B slim
""")


if __name__ == "__main__":
    main()
