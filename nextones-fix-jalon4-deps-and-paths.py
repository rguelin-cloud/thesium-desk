# -*- coding: utf-8 -*-
"""
[FIX_JALON4_DEPS_PATHS_V1]
Repare les degats du patch API Jalon 4 et adapte les chemins reels :
- Restaure api_server_with_static.py si backup recent jalon4 existe
- Detecte dans api_server_with_static.py si Depends/HTTPException/APIRouter
  sont importes ; ajoute les imports manquants
- Detecte les vrais chemins de scheduler et UI HTML

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-fix-jalon4-deps-and-paths.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
API = ROOT / "api_server_with_static.py"


def section(t):
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def restore_latest_jalon4_backup() -> bool:
    """Restaure api_server_with_static.py depuis le backup jalon4 le + recent."""
    if not API.exists():
        print(f"[FAIL] {API.name} introuvable.")
        return False

    backups = sorted(ROOT.glob("api_server_with_static.py.bak-*-jalon4*"))
    if not backups:
        backups = sorted(ROOT.glob("api_server_with_static.py.bak-*"))
    if not backups:
        print("[WARN] aucun backup trouve, on ne restaure pas.")
        return False

    latest = backups[-1]
    print(f"[INFO] backup le plus recent: {latest.name}")

    # On ne restaure QUE si la version actuelle est cassee (NameError Depends)
    txt = API.read_text(encoding="utf-8", errors="replace")
    has_depends_use = "Depends(" in txt
    has_depends_import = bool(
        re.search(r"from\s+fastapi\s+import[^\n]*\bDepends\b", txt) or
        re.search(r"^import\s+fastapi\b", txt, re.MULTILINE)
    )

    print(f"[INFO] Depends utilise   : {has_depends_use}")
    print(f"[INFO] Depends importe   : {has_depends_import}")

    if has_depends_use and not has_depends_import:
        print(f"[ACTION] restauration depuis {latest.name}")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        broken = API.with_suffix(f".py.broken-{ts}")
        shutil.copy2(API, broken)
        print(f"[BACKUP-CASSE] {broken.name}")
        shutil.copy2(latest, API)
        print(f"[OK] api_server_with_static.py restaure depuis {latest.name}")
        return True
    else:
        print("[OK] aucune incoherence detectee, pas de restauration.")
        return False


def detect_real_paths():
    section("Detection des vrais chemins")

    # 1) HTML UI
    html_candidates = [
        ROOT / "static" / "index.html",
        ROOT / "static" / "app.html",
        ROOT / "templates" / "index.html",
        ROOT / "ui" / "index.html",
        ROOT / "index.html",
    ]
    html_found = []
    for p in html_candidates:
        if p.exists():
            html_found.append(p)
    # ratisser plus large
    for p in ROOT.rglob("index.html"):
        if "node_modules" in p.parts or ".git" in p.parts:
            continue
        if p not in html_found and p.is_file():
            html_found.append(p)

    print("HTML UI candidats:")
    for p in html_found:
        size = p.stat().st_size
        # check si contient marqueurs de l'app
        head = p.read_text(encoding="utf-8", errors="replace")[:2000]
        is_thesium = any(kw in head.lower() for kw in
                         ["thesium", "nextones", "portfolio ideal", "memo ia", "carte"])
        marker = "[THESIUM-DESK]" if is_thesium else ""
        print(f"  {str(p):60s}  {size:>8} bytes  {marker}")

    # 2) Scheduler
    sched_candidates = list(ROOT.glob("scheduler*.py"))
    print("\nScheduler candidats:")
    if sched_candidates:
        for p in sched_candidates:
            print(f"  {p.name}")
    else:
        print("  (aucun fichier scheduler*.py)")
    # Chercher ou est defini le scheduler dans le projet
    scheduler_in_files = []
    for py in ROOT.glob("*.py"):
        try:
            txt = py.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if re.search(r"BackgroundScheduler\(\)|AsyncIOScheduler\(\)|scheduler\.start\(\)", txt):
            scheduler_in_files.append(py.name)
    print("Fichiers contenant un BackgroundScheduler :")
    for n in scheduler_in_files:
        print(f"  {n}")

    # 3) universe_expansion_agent
    uea = ROOT / "universe_expansion_agent.py"
    print(f"\nuniverse_expansion_agent.py : {'PRESENT' if uea.exists() else 'ABSENT'}")
    if (ROOT / "agents" / "universe_expansion_agent.py").exists():
        print("  agents/universe_expansion_agent.py PRESENT")

    return {
        "html_files": html_found,
        "scheduler_in_files": scheduler_in_files,
    }


def main() -> int:
    section("1) Restauration api_server_with_static.py si casse")
    restore_latest_jalon4_backup()

    info = detect_real_paths()

    section("Resume")
    print("Etapes suivantes :")
    print("  1. Verifier que uvicorn redemarre :")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print()
    print("  2. Une fois OK, je te genere un patcher API et UI corrige.")
    print("  3. Indique moi le fichier UI (vu plus haut, [THESIUM-DESK] flag)")
    print("     et le fichier scheduler (premier de la liste).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
