# [FRED_GDP_LABEL_V1]
# Renomme l'event GDP de "GDP (Advance Estimate)" en "GDP (Estimate)" car FRED rid=53
# publie 3 fois par trimestre : Advance (M+1), Second (M+2), Third (M+3).
# Le label "Advance" induisait en erreur : ce qu'on voit a M+2 et M+3 sont des revisions.
#
# La valeur affichee reste correcte (A191RL1Q225SBEA renvoie la derniere valeur publiee).
#
# Idempotent. Backup auto.

from pathlib import Path
import re
import shutil
import time

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
MARKER = "[FRED_GDP_LABEL_V1]"


def main():
    if not TARGET.exists():
        print(f"[ERR] {TARGET} introuvable")
        return

    raw = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] Taille avant : {len(raw)} chars")

    if MARKER in raw:
        print(f"[OK] Marker {MARKER} deja present, rien a faire.")
        return

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(f".py.bak.{ts}")
    shutil.copy2(TARGET, backup)
    print(f"[OK] Backup : {backup}")

    old = '53:  {"event": "GDP (Advance Estimate)",         "impact": "high",   "time": "08:30 ET", "category": "growth",'
    new = '53:  {"event": "GDP (Estimate)",                 "impact": "high",   "time": "08:30 ET", "category": "growth",  # ' + MARKER

    if old not in raw:
        print(f"[ERR] Ligne cible introuvable. Recherche fallback...")
        # fallback regex
        pat = re.compile(r'53:\s*\{"event":\s*"GDP \(Advance Estimate\)"', re.S)
        m = pat.search(raw)
        if m:
            print(f"      Trouve a pos={m.start()}, signature legerement differente :")
            print(f"      {raw[m.start():m.start()+150]}")
        return

    raw_new = raw.replace(old, new, 1)
    print(f"[OK] Replacement effectue (delta {len(raw_new)-len(raw):+d} chars)")

    TARGET.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK] Ecriture data_macro.py")

    # Validation
    check = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print("\n[VALIDATION]")
    tags = [
        (MARKER, 1),
        ('"event": "GDP (Estimate)"', 1),
        ('"event": "GDP (Advance Estimate)"', 0),
    ]
    all_ok = True
    for tag, expected in tags:
        n = check.count(tag)
        flag = "OK" if n == expected else "FAIL"
        if n != expected:
            all_ok = False
        print(f"  [{flag}] count={n} expected={expected} : {tag}")

    if all_ok:
        print("\n[SUCCESS] Label GDP corrige.")
        print("          Restart uvicorn recommande, puis refresh UI.")
        print("          Tu verras maintenant 'GDP (Estimate)' au lieu de 'GDP (Advance Estimate)'.")
    else:
        print("\n[FAIL] Validation incomplete.")


if __name__ == "__main__":
    main()
