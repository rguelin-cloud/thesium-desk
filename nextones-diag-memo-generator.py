"""
nextones-diag-memo-generator.py
Inspecte memo_generator.py + create_and_execute_order pour preparer le patch
[RISK_V2_WIRED].

Sortie :
  - signatures publiques de memo_generator.py
  - extrait du contexte autour de l'INSERT INTO orders (50 lignes avant + 30 apres)
  - extrait des fonctions memo qui font INSERT INTO ic_memos
  - liste des appels au risk engine existant (risk_check, single_name, sector)
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

FUNCTION_PAT = re.compile(r"^(\s*)def\s+(\w+)\s*\((.*?)\):", re.MULTILINE | re.DOTALL)


def print_signatures(path: Path):
    if not path.exists():
        print(f"[MISS] {path.name}")
        return
    src = path.read_text(encoding="utf-8-sig")
    print(f"\n=== {path.name} - signatures ===")
    for m in FUNCTION_PAT.finditer(src):
        indent = m.group(1)
        name = m.group(2)
        args = m.group(3).strip().replace("\n", " ")
        ln = src.count("\n", 0, m.start()) + 1
        scope = "module" if not indent else "method"
        print(f"   line {ln:5d}  [{scope}] def {name}({args[:120]})")


def extract_around(path: Path, pattern: str, before: int, after: int):
    if not path.exists():
        return
    src = path.read_text(encoding="utf-8-sig")
    lines = src.split("\n")
    for i, line in enumerate(lines):
        if pattern in line:
            s = max(0, i - before)
            e = min(len(lines), i + after)
            print(f"\n--- {path.name} lines {s+1}-{e} (match line {i+1}) ---")
            for j in range(s, e):
                marker = ">>> " if j == i else "    "
                print(f"{marker}{j+1:5d}  {lines[j]}")
            break


def search_calls(path: Path, patterns):
    if not path.exists():
        return
    src = path.read_text(encoding="utf-8-sig")
    lines = src.split("\n")
    print(f"\n=== {path.name} - matches calls ===")
    for i, line in enumerate(lines):
        for p in patterns:
            if p in line.lower():
                print(f"   line {i+1:5d}  {line.strip()[:160]}")
                break


def main():
    # 1. memo_generator.py - structure
    print_signatures(ROOT / "memo_generator.py")

    # 2. INSERT INTO ic_memos
    print("\n=== Recherche INSERT INTO ic_memos ===")
    for fname in ["memo_generator.py", "api_server.py", "execution_engine.py"]:
        p = ROOT / fname
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8-sig")
        for i, line in enumerate(src.split("\n")):
            if "ic_memos" in line.lower() and ("insert" in line.lower() or "into" in line.lower()):
                print(f"   {fname:30s} line {i+1}  {line.strip()[:120]}")

    # 3. Contexte autour de create_and_execute_order
    extract_around(ROOT / "execution_engine.py", "INSERT INTO orders", before=50, after=15)

    # 4. Contexte autour de la def create_and_execute_order
    extract_around(ROOT / "execution_engine.py", "def create_and_execute_order", before=2, after=30)

    # 5. Risk engine existant : appels
    search_calls(
        ROOT / "execution_engine.py",
        ["risk_check", "single_name", "sector_limit", "portfolio_var", "risk_engine"]
    )
    search_calls(
        ROOT / "risk_engine.py",
        ["def "]
    )

    # 6. memo_generator.py - extrait integral si <500 lignes
    p = ROOT / "memo_generator.py"
    if p.exists():
        src = p.read_text(encoding="utf-8-sig")
        n_lines = src.count("\n") + 1
        print(f"\n=== memo_generator.py : {n_lines} lignes ===")
        if n_lines <= 400:
            print("--- contenu integral ---")
            for i, line in enumerate(src.split("\n"), 1):
                print(f"{i:5d}  {line}")
        else:
            print(f"   (trop long, {n_lines} lignes - signatures uniquement ci-dessus)")
            # Imprime juste les 30 premieres + 30 dernieres
            lines = src.split("\n")
            print("--- 30 premieres lignes ---")
            for i, line in enumerate(lines[:30], 1):
                print(f"{i:5d}  {line}")


if __name__ == "__main__":
    main()
