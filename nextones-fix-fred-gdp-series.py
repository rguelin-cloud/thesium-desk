# [FRED_GDP_SERIES_V1]
# Fixe le bug GDP affichant 31,856.3 (niveau du PIB en milliards) au lieu de 2.0% (croissance Q/Q SAAR).
#
# Cause : RELEASE_MAP[53] utilise series_id="GDP" (niveau) + fmt="pct_chg".
#         La branche pct_chg lit obs[0] et l'affiche en %.
#         obs[0] = 31856.257 (niveau Q1 2026, milliards $) -> affichage "31,856.3".
#
# Solution : series_id="A191RL1Q225SBEA" (Real GDP, % change SAAR) + fmt="raw_pct".
#            obs[0] = 2.0 -> affichage "2.0%".
#
# Idempotent : detecte le marker.
# Backup automatique.

from pathlib import Path
import re
import shutil
import time

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
MARKER = "[FRED_GDP_SERIES_V1]"

OLD_BLOCK = (
    '        53:  {"event": "GDP (Advance Estimate)",         "impact": "high",   "time": "08:30 ET", "category": "growth",\n'
    '              "series": "GDP",      "fmt": "pct_chg", "unit": "% QoQ"},'
)

NEW_BLOCK = (
    '        # === ' + MARKER + ' : series=A191RL1Q225SBEA (Real GDP % chg SAAR), fmt=raw_pct ===\n'
    '        53:  {"event": "GDP (Advance Estimate)",         "impact": "high",   "time": "08:30 ET", "category": "growth",\n'
    '              "series": "A191RL1Q225SBEA",      "fmt": "raw_pct", "unit": "% SAAR"},'
)


def main():
    if not TARGET.exists():
        print(f"[ERR] {TARGET} introuvable")
        return

    raw = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] Fichier : {TARGET}")
    print(f"[INFO] Taille avant : {len(raw)} chars")

    # Idempotence
    if MARKER in raw:
        print(f"[OK] Marker {MARKER} deja present, rien a faire (idempotent).")
        # Sanity check : verifier que A191RL1Q225SBEA est bien la
        if '"series": "A191RL1Q225SBEA"' in raw:
            print("[OK] Patch deja applique correctement.")
        else:
            print("[WARN] Marker present mais series n'est pas A191RL1Q225SBEA. Verifie manuellement.")
        return

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(f".py.bak.{ts}")
    shutil.copy2(TARGET, backup)
    print(f"[OK]   Backup : {backup}")

    # Verifie que le bloc cible existe (recherche tolerante aux espaces)
    # On va localiser par regex pour etre robuste aux variations d'espaces
    pattern = re.compile(
        r'53:\s*\{"event":\s*"GDP \(Advance Estimate\)".*?'
        r'"series":\s*"GDP"\s*,\s*"fmt":\s*"pct_chg"\s*,\s*"unit":\s*"% QoQ"\s*\},',
        re.S,
    )
    m = pattern.search(raw)
    if not m:
        print("[ERR] Bloc GDP rid=53 introuvable avec le pattern attendu.")
        print("      Recherche fallback : 'GDP (Advance Estimate)' ...")
        if 'GDP (Advance Estimate)' in raw:
            # Localiser approximativement pour debug
            idx = raw.index('GDP (Advance Estimate)')
            print("      Bloc trouve, mais signature differente. Extrait :")
            print(raw[idx:idx + 300])
        return

    old_str = m.group(0)
    new_str = (
        '# === ' + MARKER + ' : series=A191RL1Q225SBEA (Real GDP % chg SAAR), fmt=raw_pct ===\n        '
        '53:  {"event": "GDP (Advance Estimate)",         "impact": "high",   "time": "08:30 ET", "category": "growth",\n'
        '              "series": "A191RL1Q225SBEA",      "fmt": "raw_pct", "unit": "% SAAR"},'
    )
    raw_new = raw.replace(old_str, new_str, 1)
    print(f"[OK]   Bloc remplace (delta {len(raw_new) - len(raw):+d} chars)")

    print(f"[INFO] Taille apres : {len(raw_new)} chars")
    TARGET.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK]   Ecriture data_macro.py (utf-8 sans BOM)")

    # Validation
    check = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print("\n[VALIDATION]")
    tags = [
        (MARKER, 1),
        ('"series": "A191RL1Q225SBEA"', 1),
        ('"series": "GDP",      "fmt": "pct_chg"', 0),
    ]
    all_ok = True
    for tag, expected in tags:
        n = check.count(tag)
        flag = "OK" if n == expected else "FAIL"
        if n != expected:
            all_ok = False
        print(f"  [{flag}] count={n} expected={expected} : {tag[:80]}")

    if all_ok:
        print("\n[SUCCESS] Bug FRED GDP fixe.")
        print("          Recommande : restart uvicorn pour purger le cache.")
        print("\n          Test : refresh onglet macro.")
        print("          GDP doit afficher 'actual' = '2.0' (% SAAR Q1 2026).")
        print("          Precedent doit afficher '0.5' (% SAAR Q4 2025).")
    else:
        print("\n[FAIL] Validation incomplete.")


if __name__ == "__main__":
    main()
