# [FRED_IS_PAST_DATETIME_V1]
# Fixe le bug "actual affiche avant la publication" dans data_macro.py.
#
# Probleme : _is_past = date <= today.isoformat() est vrai des minuit le jour J,
#            alors que la publication FRED est a 08:30 ET = 14:30 CEST.
# Solution : remplacer par une comparaison datetime UTC-aware qui prend
#            en compte l'heure de release codee dans RELEASE_MAP (ex: "08:30 ET").
#
# - Ajoute une fonction helper _release_datetime_utc(date_str, time_et_str)
#   qui parse "YYYY-MM-DD" + "HH:MM ET" -> datetime UTC.
# - Remplace les 5 definitions de _is_past par un appel a cette helper.
# - Idempotent : detecte le marker et reapplique proprement.
# - Backup automatique.
#
# Usage : py -3.13 nextones-fix-fred-is-past-datetime.py

from pathlib import Path
import re
import shutil
import time

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
MARKER = "[FRED_IS_PAST_DATETIME_V1]"

HELPER_BLOCK = f'''
# === {MARKER} BEGIN ===
def _release_datetime_utc(date_str: str, time_et_str: str):
    """Parse 'YYYY-MM-DD' + 'HH:MM ET' -> datetime UTC.
    'ET' = US/Eastern, gere DST automatiquement via zoneinfo.
    Retourne None si parsing echoue.
    """
    try:
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo  # py < 3.9
        # Parse 'HH:MM ET' ou 'HH:MM AM/PM ET'
        s = str(time_et_str or "").strip().upper().replace(" ET", "").strip()
        # Formats supportes : '08:30', '8:30', '14:00', '8:30 AM', '2:00 PM'
        fmts = ["%H:%M", "%I:%M %p", "%I:%M%p"]
        t = None
        for fmt in fmts:
            try:
                t = datetime.strptime(s, fmt).time()
                break
            except ValueError:
                continue
        if t is None:
            return None
        d = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        et = ZoneInfo("America/New_York")
        utc = ZoneInfo("UTC")
        return datetime.combine(d, t, tzinfo=et).astimezone(utc)
    except Exception:
        return None


def _is_release_past(date_str: str, time_et_str: str) -> bool:
    """True si la release (date + heure ET) est deja passee par rapport a now UTC."""
    from datetime import datetime, timezone
    dt = _release_datetime_utc(date_str, time_et_str)
    if dt is None:
        # fallback : comparaison sur la date pure (comportement legacy)
        try:
            from datetime import date as _date
            return str(date_str) <= _date.today().isoformat()
        except Exception:
            return False
    return dt <= datetime.now(timezone.utc)
# === {MARKER} END ===
'''


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

    # 1) Retire ancien helper s'il existe (idempotence)
    raw = re.sub(
        r"\n?# === \[FRED_IS_PAST_DATETIME_V1\] BEGIN ===.*?# === \[FRED_IS_PAST_DATETIME_V1\] END ===\n?",
        "",
        raw,
        flags=re.DOTALL,
    )

    # 2) Injecte le helper apres le dernier import du module (en haut)
    head = raw[:5000]
    last_import = None
    for m in re.finditer(r"^(import|from)\s+\S+.*$", head, re.M):
        last_import = m
    if not last_import:
        print("[ERR] Aucun import detecte en tete de module")
        return
    insert_pos = last_import.end()
    raw_new = raw[:insert_pos] + "\n" + HELPER_BLOCK + raw[insert_pos:]
    print(f"[OK]   Helper injecte apres pos={insert_pos}")

    # 3) Remplace les 5 definitions de _is_past
    # Patterns observes :
    #   "_is_past": d <= today.isoformat(),
    #   "_is_past": th_str <= today.isoformat(),
    #   "_is_past": fd <= today.isoformat(),
    #   "_is_past": prelim.isoformat() <= today.isoformat(),
    #   "_is_past": final.isoformat() <= today.isoformat(),
    # Pour chacune, on a access a 'info["time"]' (depuis RELEASE_MAP) dans la closure.
    # Remplacement uniforme : _is_release_past(<date_expr>, info.get("time"))
    replacements = [
        ('"_is_past": d <= today.isoformat()',
         '"_is_past": _is_release_past(d, info.get("time"))'),
        ('"_is_past": th_str <= today.isoformat()',
         '"_is_past": _is_release_past(th_str, info.get("time"))'),
        ('"_is_past": fd <= today.isoformat()',
         '"_is_past": _is_release_past(fd, info.get("time"))'),
        ('"_is_past": prelim.isoformat() <= today.isoformat()',
         '"_is_past": _is_release_past(prelim.isoformat(), info.get("time"))'),
        ('"_is_past": final.isoformat() <= today.isoformat()',
         '"_is_past": _is_release_past(final.isoformat(), info.get("time"))'),
    ]
    replaced_count = 0
    for old, new in replacements:
        if old in raw_new:
            raw_new = raw_new.replace(old, new, 1)
            replaced_count += 1
            print(f"  [OK] Remplacement : {old[:60]}...")
        else:
            print(f"  [WARN] Pattern introuvable : {old[:60]}...")

    if replaced_count < 5:
        print(f"[WARN] Seulement {replaced_count}/5 remplacements effectues.")
        print("       Verifie manuellement les definitions _is_past dans data_macro.py")

    print(f"[INFO] Taille apres : {len(raw_new)} chars (delta {len(raw_new)-len(raw):+d})")
    TARGET.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK]   Ecriture data_macro.py (utf-8 sans BOM)")

    # Validation
    check = TARGET.read_text(encoding="utf-8-sig", errors="replace")
    print("\n[VALIDATION]")
    tags = [
        (f"# === {MARKER} BEGIN ===", 1),
        (f"# === {MARKER} END ===", 1),
        ("def _release_datetime_utc(", 1),
        ("def _is_release_past(", 1),
        ('_is_release_past(d, info.get("time"))', 1),
        ('_is_release_past(th_str, info.get("time"))', 1),
        ('_is_release_past(fd, info.get("time"))', 1),
        ('_is_release_past(prelim.isoformat(), info.get("time"))', 1),
        ('_is_release_past(final.isoformat(), info.get("time"))', 1),
    ]
    all_ok = True
    for tag, expected in tags:
        n = check.count(tag)
        flag = "OK" if n == expected else "FAIL"
        if n != expected:
            all_ok = False
        print(f"  [{flag}] count={n:>2} expected={expected} : {tag[:60]}")

    # Verifie qu'il ne reste aucune definition legacy
    legacy = re.findall(r'"_is_past":\s*\w+\s*<=\s*today\.isoformat\(\)', check)
    if legacy:
        print(f"  [FAIL] {len(legacy)} definitions legacy encore presentes :")
        for l in legacy:
            print(f"         {l}")
        all_ok = False
    else:
        print("  [OK] Aucune definition legacy '<= today.isoformat()' restante")

    if all_ok:
        print("\n[SUCCESS] Bug FRED is_past fixe.")
        print("          Plus de restart uvicorn necessaire si le module est reimporte au prochain call.")
        print("          Recommande : restart uvicorn pour etre sur.")
        print("\n          Test : refresh ton onglet macro avant 14:30 CEST.")
        print("          GDP / Initial Jobless doivent afficher 'actual' = '—' (vide).")
        print("          A partir de 14:30 CEST : 'actual' s'affichera avec la valeur FRED reelle.")
    else:
        print("\n[FAIL] Validation incomplete.")


if __name__ == "__main__":
    main()
