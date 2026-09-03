# -*- coding: utf-8 -*-
"""
[FIND_CYCLE_FUNC_V1]
Localise la fonction appelee par l'endpoint /api/run-agents et l'execute
en local pour capter la stack trace complete du HTTP 500.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-find-cycle-func.py
"""
import os
import re
import sys
import sqlite3
import traceback
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def section(t: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


# ---------------------------------------------------------------------------
# 1) Trouver le bloc endpoint /api/run-agents dans api_server_with_static.py
# ---------------------------------------------------------------------------
def find_endpoint_body() -> str | None:
    api_file = ROOT / "api_server_with_static.py"
    if not api_file.exists():
        print(f"[FAIL] {api_file} introuvable.")
        return None

    src = api_file.read_text(encoding="utf-8", errors="replace")
    # Cherche la route
    m = re.search(r'@app\.(?:post|get)\(\s*[\'"]/api/run-agents[\'"]', src)
    if not m:
        print("[FAIL] route /api/run-agents introuvable.")
        return None

    start = m.start()
    # On prend 4000 chars apres pour avoir la fonction complete
    block = src[start : start + 4000]
    return block


def extract_call_names(block: str) -> list[str]:
    """Extrait les noms de fonctions appelees dans le handler."""
    # Pattern: word(  -- skip mots-cles
    names = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", block)
    skip = {
        "def", "async", "await", "if", "for", "while", "return", "print",
        "str", "int", "float", "dict", "list", "tuple", "set", "bool",
        "len", "range", "isinstance", "getattr", "setattr", "open",
        "Depends", "HTTPException", "BackgroundTasks", "Query", "Body",
        "JSONResponse", "datetime", "timedelta", "Path", "True", "False",
        "None", "Exception", "ValueError", "TypeError",
    }
    out = []
    seen = set()
    for n in names:
        if n in skip or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


# ---------------------------------------------------------------------------
# 2) Imports en haut du fichier (pour savoir d'ou viennent les fonctions)
# ---------------------------------------------------------------------------
def find_imports_for(name: str) -> str | None:
    api_file = ROOT / "api_server_with_static.py"
    src = api_file.read_text(encoding="utf-8", errors="replace")
    for line in src.splitlines()[:300]:
        if (f"import {name}" in line) or (f", {name}" in line and "import" in line) \
           or re.search(rf"\bfrom\s+\S+\s+import\s+[^#]*\b{name}\b", line):
            return line.strip()
    return None


# ---------------------------------------------------------------------------
# 3) Essayer d'executer en in-proc en suivant le code reel
# ---------------------------------------------------------------------------
def try_run_handler() -> None:
    """
    Approche: appeler directement la fonction handler en simulant le user.
    On importe api_server_with_static et on cherche un attribut sur app.
    """
    try:
        import importlib
        api_mod = importlib.import_module("api_server_with_static")
        print("[OK] api_server_with_static importe.")

        # Cherche les noms de fonctions definies dans le module
        cand_names = []
        for name in dir(api_mod):
            if name.lower().startswith(("run_", "execute_", "cycle", "agents")):
                obj = getattr(api_mod, name)
                if callable(obj):
                    cand_names.append(name)
        print(f"Candidats dans api_server: {cand_names}")

        # Cherche dans agents.*
        try:
            import agents
            for name in dir(agents):
                if name.lower().startswith(("run_", "execute_", "cycle", "decision")):
                    obj = getattr(agents, name)
                    if callable(obj):
                        cand_names.append(f"agents.{name}")
        except Exception as e:
            print(f"(import agents: {e})")
        print(f"Candidats etendus: {cand_names}")

    except Exception:
        print("[FAIL] import api_server_with_static a echoue:")
        traceback.print_exc()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main() -> int:
    section("1) Handler /api/run-agents — code source")
    block = find_endpoint_body()
    if block:
        # Affiche les 60 premieres lignes du handler
        for i, line in enumerate(block.splitlines()[:60], 1):
            print(f"{i:3d}  {line}")

        section("2) Fonctions appelees dans le handler")
        names = extract_call_names(block)
        print(names[:30])

        section("3) Imports pour ces fonctions (source)")
        for n in names[:15]:
            imp = find_imports_for(n)
            if imp:
                print(f"  {n:30s} <- {imp}")

    section("4) Modules importables et candidats")
    try_run_handler()

    section("5) Derniers logs uvicorn (si presents)")
    for cand in [ROOT / "uvicorn.log", ROOT / "logs" / "uvicorn.log", ROOT / "server.log"]:
        if cand.exists():
            print(f"--- {cand} (dernieres 80 lignes) ---")
            txt = cand.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in txt[-80:]:
                print(line)
            break
    else:
        print("(pas de fichier log uvicorn trouve)")

    section("FIN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
