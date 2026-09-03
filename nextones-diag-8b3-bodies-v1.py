# -*- coding: utf-8 -*-
# nextones-diag-8b3-bodies-v1.py
# Dump des bodies critiques pour cartographier 8B.3 :
#   - fill_simulator.simulate_fill (formule slippage, open_j+1, retour)
#   - fill_simulator.compute_slippage_bps
#   - risk_pretrade.run_pretrade_checks (entrees, dependances DB, retour)
#   - replay_adapters.MarketDataAdapter (methodes pour open_j+1, get_price, etc.)
#
# Mode strict lecture-seule.

import os
import sys
import ast

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)


def sep(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def dump_function_body(filepath, func_name, class_name=None):
    """Dump le body complet d'une fonction (top-level ou methode de classe)."""
    sep(f"BODY : {filepath} :: {class_name + '.' if class_name else ''}{func_name}")
    if not os.path.exists(filepath):
        print(f"  [ABSENT]")
        return
    with open(filepath, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.splitlines()
    tree = ast.parse(src)

    def visit(node, parent_class=None):
        if isinstance(node, ast.ClassDef):
            for sub in node.body:
                visit(sub, parent_class=node.name)
        elif isinstance(node, ast.FunctionDef):
            if node.name == func_name and parent_class == class_name:
                start = node.lineno
                # end_lineno disponible depuis Python 3.8
                end = getattr(node, "end_lineno", start + 50)
                print(f"  Lines {start}-{end} :")
                for i in range(start, min(end + 1, len(lines) + 1)):
                    print(f"  L{i:4d}| {lines[i-1]}")
                return True
        for child in ast.iter_child_nodes(node):
            visit(child, parent_class=parent_class)

    visit(tree)


def dump_class(filepath, class_name):
    """Dump complet d'une classe."""
    sep(f"CLASS : {filepath} :: {class_name}")
    if not os.path.exists(filepath):
        print(f"  [ABSENT]")
        return
    with open(filepath, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.splitlines()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            start = node.lineno
            end = getattr(node, "end_lineno", start + 100)
            print(f"  Lines {start}-{end} :")
            for i in range(start, min(end + 1, len(lines) + 1)):
                print(f"  L{i:4d}| {lines[i-1]}")
            return


def dump_top_level_constants(filepath):
    """Dump les assignations top-level (DEFAULT_PARAMS, etc.)."""
    sep(f"CONSTANTES TOP-LEVEL : {filepath}")
    if not os.path.exists(filepath):
        return
    with open(filepath, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.splitlines()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            for i in range(start, min(end + 1, len(lines) + 1)):
                # Limite aux constantes en MAJ
                line = lines[i-1]
                if any(c.isupper() for c in line[:20]):
                    print(f"  L{i:4d}| {line}")


def main():
    print(f"PROD_DIR : {PROD_DIR}")

    fill_path = os.path.join(PROD_DIR, "fill_simulator.py")
    risk_path = os.path.join(PROD_DIR, "risk_pretrade.py")
    adapters_path = os.path.join(PROD_DIR, "replay_adapters.py")

    # 1. fill_simulator
    dump_function_body(fill_path, "simulate_fill")
    dump_function_body(fill_path, "compute_slippage_bps")
    dump_class(fill_path, "FillResult")

    # 2. risk_pretrade
    dump_function_body(risk_path, "run_pretrade_checks")
    dump_top_level_constants(risk_path)

    # 3. replay_adapters - MarketDataAdapter
    if os.path.exists(adapters_path):
        # Liste toutes les classes + methodes
        sep(f"replay_adapters.py - signature complete")
        with open(adapters_path, "r", encoding="utf-8-sig") as f:
            src = f.read()
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                print(f"  class {node.name}:")
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef):
                        args = [a.arg for a in sub.args.args]
                        print(f"      def {sub.name}({', '.join(args)})")
            elif isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                print(f"  def {node.name}({', '.join(args)})")
        # Body de get_price / get_open / get_close
        for fname in ["get_price", "get_open", "get_close", "get_open_j1", "get_volume"]:
            dump_function_body(adapters_path, fname, class_name="MarketDataAdapter")
    else:
        print("  [replay_adapters.py absent]")

    # 4. execution_engine.create_and_execute_order (pour voir le workflow standard)
    exec_path = os.path.join(PROD_DIR, "execution_engine.py")
    dump_function_body(exec_path, "create_and_execute_order")

    print()
    print("=" * 72)
    print("DIAG bodies 8B.3 termine.")
    print("=" * 72)


if __name__ == "__main__":
    main()
