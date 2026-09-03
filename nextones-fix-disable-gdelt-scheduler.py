# [GDELT_SCHEDULER_DISABLED_V1]
# Desactive le job scheduler 'refresh_geo' qui appelle GDELT/USGS en boucle
# et provoque les rate limits 429 + ~400s de pre-fetch au startup.
#
# - Commente la ligne `scheduler.add_job(refresh_geo, ...)` dans api_server.py
# - Garde le job refresh_pplx_geo intact (c'est le panel Perplexity actif)
# - Marker idempotent : la ligne devient
#       # [GDELT_SCHEDULER_DISABLED_V1] scheduler.add_job(refresh_geo, ...)
#
# Reversible : decommente la ligne et restart uvicorn.
# Backup automatique avant modification.
#
# Usage : py -3.13 nextones-fix-disable-gdelt-scheduler.py

from pathlib import Path
import re
import shutil
import time

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
MARKER = "[GDELT_SCHEDULER_DISABLED_V1]"


def main():
    if not TARGET.exists():
        print(f"[ERR] {TARGET} introuvable")
        return

    raw = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] Fichier : {TARGET}")
    print(f"[INFO] Taille avant : {len(raw)} chars")

    # Verifie que le code n'est pas deja desactive
    if MARKER in raw:
        print(f"[OK]   {MARKER} deja present, idempotent : on regenere proprement.")
        # Pour idempotence, on retire d'abord toute version precedemment commentee,
        # puis on re-applique.
        # Pattern : ligne commencee par "# [GDELT_SCHEDULER_DISABLED_V1] " contenant refresh_geo
        raw = re.sub(
            r"^\s*#\s*\[GDELT_SCHEDULER_DISABLED_V1\][^\n]*scheduler\.add_job\(\s*refresh_geo[^\n]*\n",
            "",
            raw,
            flags=re.M,
        )

    # Cherche la ligne `scheduler.add_job(refresh_geo, ...)` (refresh_geo seul, pas refresh_pplx_geo)
    # Use negative lookahead pour exclure refresh_pplx_geo
    pattern = re.compile(
        r"(^[ \t]*)scheduler\.add_job\(\s*refresh_geo\b(?!_pplx)(?!.*pplx)[^\n]*\n",
        re.M,
    )
    matches = list(pattern.finditer(raw))
    if not matches:
        # Tente version alternative : recherche stricte sur refresh_geo NON suivi de _pplx
        pattern = re.compile(
            r"(^[ \t]*)scheduler\.add_job\(\s*refresh_geo\s*,[^\n]*\n",
            re.M,
        )
        matches = list(pattern.finditer(raw))

    if not matches:
        print("[ERR] Ligne `scheduler.add_job(refresh_geo, ...)` introuvable. Abort.")
        print("      Verifie manuellement L139 de api_server.py")
        return

    if len(matches) > 1:
        print(f"[WARN] {len(matches)} occurrences trouvees, on ne traite que la premiere.")

    m = matches[0]
    print(f"[OK]   Cible localisee a l'offset {m.start()}")
    original_line = m.group(0).rstrip("\n")
    indent = m.group(1)
    print(f"[OK]   Ligne originale : {original_line.strip()[:120]}")

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(f".py.bak.{ts}")
    shutil.copy2(TARGET, backup)
    print(f"[OK]   Backup : {backup}")

    # Construit la ligne de remplacement : commentee avec marker
    new_line = f"{indent}# {MARKER} desactive (GDELT rate-limit 429) : {original_line.strip()}\n"

    raw_new = raw[: m.start()] + new_line + raw[m.end():]
    print(f"[INFO] Taille apres : {len(raw_new)} chars (delta {len(raw_new)-len(raw):+d})")

    TARGET.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK]   Ecriture api_server.py (utf-8 sans BOM)")

    # Validation
    check = TARGET.read_text(encoding="utf-8-sig", errors="replace")

    # 1) Le marker doit etre present
    n_marker = check.count(MARKER)
    # 2) La ligne ACTIVE refresh_geo (sans #) ne doit plus exister
    active = re.search(r"^[ \t]*scheduler\.add_job\(\s*refresh_geo\s*,", check, re.M)
    # 3) La ligne refresh_pplx_geo doit etre intacte
    pplx_active = re.search(r"^[ \t]*scheduler\.add_job\(\s*refresh_pplx_geo\s*,", check, re.M)

    print("\n[VALIDATION]")
    print(f"  [{'OK' if n_marker >= 1 else 'MISS'}] {MARKER} present count={n_marker}")
    print(f"  [{'OK' if active is None else 'FAIL'}] Ligne refresh_geo active : {'NON (correct)' if active is None else 'OUI (probleme)'}")
    print(f"  [{'OK' if pplx_active else 'MISS'}] Ligne refresh_pplx_geo active : {'OUI (correct)' if pplx_active else 'NON (probleme)'}")

    if n_marker >= 1 and active is None and pplx_active is not None:
        print("\n[SUCCESS] Job GDELT desactive proprement.")
        print("          Restart uvicorn :")
        print("            py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
        print("          Au startup : plus de pre-fetch GDELT/USGS, plus de 429.")
        print("          refresh_pplx_geo continue de tourner (toutes les 4h).")
    else:
        print("\n[FAIL] Validation echouee, examine les flags ci-dessus.")


if __name__ == "__main__":
    main()
