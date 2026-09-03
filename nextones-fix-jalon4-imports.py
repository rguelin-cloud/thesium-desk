# -*- coding: utf-8 -*-
"""
[FIX_JALON4_IMPORTS_V1]
Adapte les fichiers Jalon 4 a l'arbo reelle de ThesiumDesk :
- Pas de package agents/, tout au niveau racine
- pplx_client.py, agents.py, etc. sont a la racine

Actions :
1) Copie nextones-universe-expansion-agent.py -> universe_expansion_agent.py (racine)
   en remplacant 'from agents.pplx_client' -> 'from pplx_client'
2) Patche nextones-api-universe-endpoints.py pour utiliser 'from universe_expansion_agent'
3) Patche nextones-scheduler-universe-monthly.py pareil

Idempotent (verifie marker FIX_JALON4_IMPORTS_V1 dans chaque fichier patche).

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-fix-jalon4-imports.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
MARKER = "# [FIX_JALON4_IMPORTS_V1]"


def section(t):
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def patch_file(src_path: Path, dst_path: Path, replacements: list[tuple[str, str]]) -> None:
    """Lit src, remplace, ecrit dans dst. Backup si dst existe."""
    if not src_path.exists():
        print(f"[SKIP] {src_path.name} introuvable.")
        return

    txt = src_path.read_text(encoding="utf-8-sig", errors="replace")

    # Si deja patche -> skip
    if MARKER in txt and src_path == dst_path:
        print(f"[SKIP] {dst_path.name} deja patche.")
        return

    # Appliquer remplacements
    n = 0
    for old, new in replacements:
        if old in txt:
            txt = txt.replace(old, new)
            n += 1

    # Inserer marker en haut (apres docstring eventuel)
    if MARKER not in txt:
        # injecter sur la 2e ligne (apres # -*- encoding -*- eventuel)
        lines = txt.splitlines(keepends=True)
        insert_at = 0
        for i, ln in enumerate(lines[:5]):
            if ln.startswith("#") or ln.strip() == "":
                insert_at = i + 1
            else:
                break
        lines.insert(insert_at, f"{MARKER}\n")
        txt = "".join(lines)

    # Backup destination si existe et diff src
    if dst_path.exists() and dst_path != src_path:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = dst_path.with_suffix(f"{dst_path.suffix}.bak-{ts}-jalon4-imports")
        shutil.copy2(dst_path, bak)
        print(f"[BACKUP] {bak.name}")

    dst_path.write_text(txt, encoding="utf-8")
    print(f"[OK]    {dst_path.name}  ({n} remplacement(s))")


def main() -> int:
    section("1) Copie + adapte universe_expansion_agent vers la racine")
    patch_file(
        src_path=ROOT / "nextones-universe-expansion-agent.py",
        dst_path=ROOT / "universe_expansion_agent.py",
        replacements=[
            ("from agents.pplx_client import PerplexityClient",
             "from pplx_client import PerplexityClient"),
            ("from agents.pplx_client",
             "from pplx_client"),
            ("import agents.pplx_client",
             "import pplx_client"),
        ],
    )

    section("2) Patche le script d'install API endpoints")
    patch_file(
        src_path=ROOT / "nextones-api-universe-endpoints.py",
        dst_path=ROOT / "nextones-api-universe-endpoints.py",
        replacements=[
            ("from agents.universe_expansion_agent import",
             "from universe_expansion_agent import"),
            ("agents.universe_expansion_agent",
             "universe_expansion_agent"),
        ],
    )

    section("3) Patche le script d'install scheduler")
    patch_file(
        src_path=ROOT / "nextones-scheduler-universe-monthly.py",
        dst_path=ROOT / "nextones-scheduler-universe-monthly.py",
        replacements=[
            ("from agents.universe_expansion_agent import run_scan as _universe_scan",
             "from universe_expansion_agent import run_scan as _universe_scan"),
            ("from agents.universe_expansion_agent",
             "from universe_expansion_agent"),
            ("agents.universe_expansion_agent",
             "universe_expansion_agent"),
        ],
    )

    section("4) Patche le script de verification")
    patch_file(
        src_path=ROOT / "nextones-verify-jalon4.py",
        dst_path=ROOT / "nextones-verify-jalon4.py",
        replacements=[
            ("from agents.universe_expansion_agent import",
             "from universe_expansion_agent import"),
            ("agents.universe_expansion_agent",
             "universe_expansion_agent"),
            ("agents/universe_expansion_agent.py",
             "universe_expansion_agent.py"),
        ],
    )

    section("5) Verification")
    target = ROOT / "universe_expansion_agent.py"
    if target.exists():
        head = target.read_text(encoding="utf-8")[:500]
        print("Premieres lignes de universe_expansion_agent.py:")
        for ln in head.splitlines()[:15]:
            print(f"  {ln}")
        # check imports
        if "from agents.pplx_client" in target.read_text(encoding="utf-8"):
            print("[WARN] reste un import 'from agents.pplx_client' a corriger manuellement.")
        else:
            print("[OK] imports adaptes a la racine.")

    print()
    print("Prochaines etapes :")
    print("  py -3.13 nextones-api-universe-endpoints.py")
    print("  py -3.13 nextones-scheduler-universe-monthly.py")
    print("  py -3.13 nextones-ui-universe-candidates-card.py")
    print("  # redemarrer uvicorn")
    print("  py -3.13 nextones-verify-jalon4.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
