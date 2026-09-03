"""
[DIAG_MEMO_STRUCTURE]
Inspection ciblee de memo_generator.py :
 - tout le bloc L230 a L350 brut, pour voir EXACTEMENT la structure
   apres patch (def manquante ? imbrication ? indentation cassee ?)
"""
from pathlib import Path

FP = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py")

def main():
    src = FP.read_text(encoding="utf-8-sig")
    lines = src.splitlines()
    print(f"[INFO] total lignes = {len(lines)}")
    print()
    print("=" * 70)
    print("DUMP brut L225-L345 (inclus)")
    print("=" * 70)
    for i in range(224, min(345, len(lines))):
        # numero + indent visible
        ln = lines[i]
        # caractere de fin de ligne visible (pas de \r\n cache)
        n_lead = len(ln) - len(ln.lstrip())
        print(f"L{i+1:4d}|{n_lead:2d}|{ln}")
    print()
    print("=" * 70)
    print("DUMP brut L370-L400 (apres la zone risk_v2)")
    print("=" * 70)
    for i in range(369, min(400, len(lines))):
        ln = lines[i]
        n_lead = len(ln) - len(ln.lstrip())
        print(f"L{i+1:4d}|{n_lead:2d}|{ln}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
