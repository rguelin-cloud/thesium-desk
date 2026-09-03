# [GDELT_MODULE_DISABLED_V1]
# Desactive proprement TOUS les appels GDELT/USGS au niveau du module
# data_geopolitical.py en interceptant les deux points d'entree publics :
#   - start_background_fetch()    -> return early (pas de thread daemon GDELT)
#   - fetch_geopolitical_risk()   -> renvoie payload vide marquant "disabled"
#
# Methode : injection en tete de chaque fonction d'un guard
#     if _GDELT_DISABLED: return ...
# avec une constante globale _GDELT_DISABLED = True placee en haut du module.
#
# Marker idempotent : [GDELT_MODULE_DISABLED_V1]
# Backup automatique avant patch.
# Reversible : passer _GDELT_DISABLED = False (ou supprimer le bloc marker).
#
# Usage : py -3.13 nextones-fix-disable-gdelt-module.py

from pathlib import Path
import re
import shutil
import time

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_geopolitical.py")
MARKER = "[GDELT_MODULE_DISABLED_V1]"
TOGGLE_VAR = "_GDELT_DISABLED"

# Bloc constante a injecter pres du sommet du module
TOGGLE_BLOCK = f"""
# === {MARKER} BEGIN ===
# Toggle global pour desactiver tous les appels GDELT/USGS.
# Mettre a False pour reactiver (les threads daemon GDELT redemarreront au prochain
# call de start_background_fetch). Reglez via env si besoin :
#   os.environ['NEXTONES_GDELT_DISABLED'] = '1'
import os as _os_gdelt
{TOGGLE_VAR} = _os_gdelt.environ.get("NEXTONES_GDELT_DISABLED", "1") not in ("0", "false", "False", "")
# === {MARKER} END ===
"""

# Guards a injecter en tete des deux fonctions publiques
GUARD_BG = f"""    # === {MARKER} guard BEGIN ===
    if {TOGGLE_VAR}:
        # GDELT/USGS desactives volontairement (rate-limit 429 chronique).
        # Le panel Perplexity 'Contexte geopolitique IA' couvre cette fonction.
        print("[GEO] start_background_fetch() : DISABLED (toggle {TOGGLE_VAR}=True)")
        return
    # === {MARKER} guard END ===
"""

GUARD_FETCH = f"""    # === {MARKER} guard BEGIN ===
    if {TOGGLE_VAR}:
        # GDELT/USGS desactives volontairement.
        return {{
            "disabled": True,
            "reason": "GDELT/USGS module disabled ({MARKER})",
            "global_score": None,
            "regime": None,
            "theaters": [],
            "chokepoints": [],
            "alerts": [],
            "summary": "Source GDELT/USGS desactivee. Voir le panel Perplexity.",
            "_complete": True,
        }}
    # === {MARKER} guard END ===
"""


def main():
    if not TARGET.exists():
        print(f"[ERR] {TARGET} introuvable")
        return

    raw = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] Fichier : {TARGET}")
    print(f"[INFO] Taille avant : {len(raw)} chars")

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(f".py.bak.{ts}")
    shutil.copy2(TARGET, backup)
    print(f"[OK]   Backup : {backup}")

    # 1) Retire toute version precedente du toggle et des guards (idempotence)
    raw = re.sub(
        r"# === \[GDELT_MODULE_DISABLED_V1\] BEGIN ===.*?# === \[GDELT_MODULE_DISABLED_V1\] END ===\n?",
        "",
        raw,
        flags=re.DOTALL,
    )
    raw = re.sub(
        r"    # === \[GDELT_MODULE_DISABLED_V1\] guard BEGIN ===.*?# === \[GDELT_MODULE_DISABLED_V1\] guard END ===\n?",
        "",
        raw,
        flags=re.DOTALL,
    )

    # 2) Injecte le toggle juste apres le premier bloc d'imports
    # On cherche la derniere ligne 'import ...' ou 'from ... import ...' dans les 100 premieres lignes
    head = "\n".join(raw.split("\n")[:120])
    last_import_match = None
    for m in re.finditer(r"^(import|from)\s+\S+.*$", head, re.M):
        last_import_match = m
    if not last_import_match:
        # fallback : apres le shebang/docstring du module
        print("[WARN] Aucun import detecte dans les 120 premieres lignes")
        return
    insert_pos = last_import_match.end()
    # Trouve la fin de la ligne dans raw (insert_pos calcule sur head)
    raw_insert = insert_pos
    raw_new = raw[:raw_insert] + "\n" + TOGGLE_BLOCK + raw[raw_insert:]
    print(f"[OK]   Toggle injecte apres pos={raw_insert}")

    # 3) Injecte le guard dans start_background_fetch
    m = re.search(
        r"^def\s+start_background_fetch\s*\([^)]*\)\s*:\s*\n(\s*\"\"\"[^\"]*\"\"\"\s*\n)?",
        raw_new,
        re.M,
    )
    if not m:
        print("[ERR] start_background_fetch() introuvable apres injection toggle")
        return
    insert = m.end()
    raw_new = raw_new[:insert] + GUARD_BG + raw_new[insert:]
    print("[OK]   Guard injecte dans start_background_fetch()")

    # 4) Injecte le guard dans fetch_geopolitical_risk
    m = re.search(
        r"^def\s+fetch_geopolitical_risk\s*\([^)]*\)[^:]*:\s*\n(\s*\"\"\"[^\"]*\"\"\"\s*\n)?",
        raw_new,
        re.M,
    )
    if not m:
        print("[ERR] fetch_geopolitical_risk() introuvable apres injection toggle")
        return
    insert = m.end()
    raw_new = raw_new[:insert] + GUARD_FETCH + raw_new[insert:]
    print("[OK]   Guard injecte dans fetch_geopolitical_risk()")

    print(f"[INFO] Taille apres : {len(raw_new)} chars (delta {len(raw_new)-len(raw):+d})")
    TARGET.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK]   Ecriture data_geopolitical.py (utf-8 sans BOM)")

    # Validation
    check = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    checks = [
        (f"# === {MARKER} BEGIN ===", 1),
        (f"# === {MARKER} END ===", 1),
        (f"{TOGGLE_VAR} = _os_gdelt", 1),
        (f"# === {MARKER} guard BEGIN ===", 2),  # 2 guards (start_bg + fetch)
        (f"# === {MARKER} guard END ===", 2),
        (f"if {TOGGLE_VAR}:", 2),
    ]
    all_ok = True
    print("\n[VALIDATION]")
    for tag, expected in checks:
        n = check.count(tag)
        flag = "OK" if n == expected else "FAIL"
        if n != expected:
            all_ok = False
        print(f"  [{flag}] count={n} expected={expected} : {tag[:55]}")

    # Verifie que la def n'a pas ete cassee
    if "def start_background_fetch():" in check and "def fetch_geopolitical_risk()" in check:
        print("  [OK] def start_background_fetch / fetch_geopolitical_risk intactes")
    else:
        print("  [FAIL] Une des deux defs est manquante")
        all_ok = False

    if all_ok:
        print("\n[SUCCESS] Module GDELT/USGS desactive proprement.")
        print("          1) Arrete uvicorn : .\\nextones-stop-uvicorn-clean.ps1")
        print("          2) Relance       : py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
        print("          Au startup : plus aucun [GEO] / [GDELT] dans les logs.")
        print("          Les endpoints /api/geopolitical/* renvoient un payload 'disabled'.")
        print("          Reactivation : os.environ['NEXTONES_GDELT_DISABLED'] = '0' avant import,")
        print("                         ou supprimer le bloc marker.")
    else:
        print("\n[FAIL] Validation incomplete, examine les flags ci-dessus.")


if __name__ == "__main__":
    main()
