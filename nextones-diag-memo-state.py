"""
[DIAG_MEMO_STATE]
Verifie l'etat de memo_generator.py apres le patch :
 1. Le fichier existe-t-il, et taille ?
 2. Le marker [MEMO_VERDICT_REASON_FIX_V1] est-il present ?
 3. Cherche TOUTES les def autour de risk_v2 / pretrade / build / _humanize
 4. Cherche les lignes contenant 'broker_mapping_ok' / 'BLOCK' / 'verdict'
 5. Affiche les 30 premieres lignes pour valider l'encodage
"""
from pathlib import Path
import re

FP = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py")

def main():
    if not FP.exists():
        print(f"[ERR] {FP} introuvable")
        return 1
    raw = FP.read_bytes()
    print(f"[INFO] taille = {len(raw)} bytes")
    print(f"[INFO] BOM = {raw[:3] == b'\\xef\\xbb\\xbf'}")

    src = FP.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] lignes = {len(src.splitlines())}")
    print()

    print("[1] Markers presents")
    print("-" * 60)
    for marker in ("[MEMO_VERDICT_REASON_FIX_V1]", "[RISK_V2_WIRED]", "[RISK_V2]"):
        n = src.count(marker)
        print(f"   {marker:40s} x {n}")

    print()
    print("[2] Toutes les definitions de fonction (def ...)")
    print("-" * 60)
    for m in re.finditer(r"^(\s*)def\s+(\w+)\s*\([^)]*\)\s*:", src, re.MULTILINE):
        line_no = src[:m.start()].count("\n") + 1
        indent = len(m.group(1))
        print(f"   L{line_no:4d} indent={indent:2d} def {m.group(2)}")

    print()
    print("[3] Lignes contenant 'verdict' / 'BLOCK' / 'broker_mapping' / '_humanize'")
    print("-" * 60)
    for i, ln in enumerate(src.splitlines(), 1):
        low = ln.lower()
        if any(k in low for k in ("verdict", "block", "broker_mapping", "_humanize")):
            print(f"   L{i:4d}: {ln.rstrip()[:200]}")

    print()
    print("[4] Premieres 40 lignes du fichier")
    print("-" * 60)
    for i, ln in enumerate(src.splitlines()[:40], 1):
        print(f"   L{i:3d}: {ln.rstrip()[:200]}")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
