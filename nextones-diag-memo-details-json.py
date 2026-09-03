"""
[DIAG_MEMO_DETAILS_JSON]
Le fix verdict a applique le mauvais libelle ("Mapping broker OK" au lieu de
"Non tradable (regle A)"). La helper recoit details_json=None et fallback
sur blocked_by ("broker_mapping_ok").

Diag :
 1. Lire _build_risk_v2_section complet
 2. Identifier la SQL query : d'ou viennent o, row, passed, blocked, details_json
 3. Verifier si la colonne details_json est dans le SELECT (sinon o.get('details_json') = None)
"""
from pathlib import Path
import re

FP = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py")

def main():
    if not FP.exists():
        print(f"[ERR] {FP} introuvable")
        return 1
    src = FP.read_text(encoding="utf-8-sig")

    # Extraire la fonction _build_risk_v2_section
    pat = re.compile(r"^def\s+_build_risk_v2_section\s*\([^)]*\)\s*:", re.MULTILINE)
    m = pat.search(src)
    if not m:
        print("[ERR] fonction _build_risk_v2_section introuvable")
        return 1
    start = m.start()
    rest = src[m.end():]
    nxt = re.search(r"^(def|class)\s", rest, re.MULTILINE)
    end = m.end() + (nxt.start() if nxt else len(rest))
    block = src[start:end]
    print("=" * 70)
    print("FONCTION _build_risk_v2_section COMPLETE")
    print("=" * 70)
    for i, ln in enumerate(block.splitlines(), 1):
        print(f"L{i:3d}: {ln}")

    # Tester aussi le import / definition au-dessus (variables o, row, blocked, passed)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
