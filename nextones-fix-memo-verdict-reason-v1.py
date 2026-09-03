"""
[MEMO_VERDICT_REASON_FIX_V1]

Probleme :
  Le memo IC affiche "BLOCK (broker_mapping_ok)" dans le panneau
  Pre-trade Controls [RISK_V2]. C'est le NOM DU CHECK, pas le motif.
  Le vrai motif est dans details_json[blocked_by]["reason"]
  (par ex. "not_tradable_strict_refusal").

Fix :
  Dans memo_generator.py, fonction _build_risk_v2_section (autour L260) :
  Au lieu de :
      verdict = "PASS" if passed else f"BLOCK ({blocked})"
  On extrait le vrai reason + on traduit en libelle humain court :
      blocked_by   = "broker_mapping_ok"
      reason       = "not_tradable_strict_refusal"
      label        = "Non tradable (regle A strict)"
      verdict      = "BLOCK - Non tradable (regle A strict)"

  Et on ajoute un mini tooltip via une colonne "Motif" enrichie si possible.

Idempotent : marker [MEMO_VERDICT_REASON_FIX_V1].

Cibles :
  C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\memo_generator.py
"""
from __future__ import annotations
import ast
import json
import os
import py_compile
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TARGET = ROOT / "memo_generator.py"
MARKER = "[MEMO_VERDICT_REASON_FIX_V1]"

# Nouvelle helper qu'on insere AVANT _build_risk_v2_section
HELPER_BLOCK = '''
# {marker}
# Traduit un (blocked_by, details_json) en libelle humain court pour le memo IC.
# blocked_by est le NOM DU CHECK (ex: "broker_mapping_ok"), pas un motif.
# Le vrai motif se trouve dans details_json[blocked_by]["reason"].
def _humanize_block_reason(blocked_by, details_json):
    """Returns (short_reason, long_reason) for memo display."""
    import json as _json
    try:
        details = _json.loads(details_json) if isinstance(details_json, str) else (details_json or {})
    except Exception:
        details = {{}}
    sub = (details or {{}}).get(blocked_by) or {{}}
    raw_reason = sub.get("reason") or blocked_by or "unknown"

    # Mapping technique -> libelle humain FR court
    HUMAN = {{
        "not_tradable_strict_refusal":   ("Non tradable (regle A)",
                                          "Symbole non mappe chez le broker - refus strict"),
        "broker_mapping_ok":             ("Mapping broker OK",
                                          "Verification du mapping broker reussie"),
        "concentration_exceeded":        ("Concentration > 15%",
                                          "Position depasserait le plafond de concentration"),
        "var_budget_exceeded":           ("Budget VaR depasse",
                                          "L'ordre depasse le budget VaR portefeuille"),
        "correlation_excess":            ("Correlation trop forte",
                                          "Correlation 60j > seuil avec autres positions"),
        "qty_overshoot":                 ("Qty > position",
                                          "Quantite SELL superieure a la position detenue"),
        "no_position":                   ("Aucune position",
                                          "Aucune position a vendre pour ce ticker"),
        "market_closed":                 ("Marche ferme",
                                          "Hors plage horaire ou jour ferie NYSE"),
    }}
    short, long_ = HUMAN.get(raw_reason, (raw_reason, raw_reason))
    return short, long_

'''.format(marker=MARKER)


def fail(msg):
    print(f"[ERR] {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"introuvable: {TARGET}")

    src = TARGET.read_text(encoding="utf-8-sig")

    # Idempotent
    if MARKER in src:
        print(f"[SKIP] {MARKER} deja present dans memo_generator.py")
        return 0

    # Backup
    bak = TARGET.with_suffix(
        f".py.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    shutil.copyfile(TARGET, bak)
    print(f"[OK] backup -> {bak.name}")

    # 1. Inserer le helper AVANT la fonction _build_risk_v2_section
    pat_helper = re.compile(
        r"^(def\s+_build_risk_v2_section\s*\()", re.MULTILINE
    )
    m = pat_helper.search(src)
    if not m:
        fail("def _build_risk_v2_section introuvable dans memo_generator.py")
    new_src = src[: m.start()] + HELPER_BLOCK + "\n" + src[m.start() :]

    # 2. Patch de la ligne :
    #     verdict = "PASS" if passed else f"BLOCK ({blocked})"
    # vers :
    #     if passed:
    #         verdict = "PASS"
    #     else:
    #         _short, _long = _humanize_block_reason(blocked, o.get("details_json") or row.get("details_json"))
    #         verdict = f"BLOCK - {_short}"
    pat_verdict = re.compile(
        r'verdict\s*=\s*"PASS"\s+if\s+passed\s+else\s+f"BLOCK\s*\(\{blocked\}\)"'
    )
    if not pat_verdict.search(new_src):
        # tentative variante sans accolades f-string
        pat_verdict2 = re.compile(
            r'verdict\s*=\s*"PASS"\s+if\s+passed\s+else\s+f"BLOCK\s*\([^)]+\)"'
        )
        m2 = pat_verdict2.search(new_src)
        if not m2:
            fail("ligne verdict = ... BLOCK introuvable - aborter")
        old_line = m2.group(0)
    else:
        old_line = pat_verdict.search(new_src).group(0)

    new_block = (
        '_short_r, _long_r = _humanize_block_reason(blocked, '
        'o.get("details_json") if isinstance(o, dict) else None)\n'
        '            verdict = "PASS" if passed else f"BLOCK - {_short_r}"  '
        + MARKER
    )
    # On remplace la ligne (preserver l'indentation : remplace juste l'expression)
    # Pour rester safe : on injecte la nouvelle expression sur la meme ligne
    # avec un saut + indent. On detecte l'indent en remontant a la ligne.
    line_start = new_src.rfind("\n", 0, new_src.find(old_line)) + 1
    indent = ""
    for ch in new_src[line_start:]:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break
    replacement = (
        f"{indent}_short_r, _long_r = _humanize_block_reason("
        f"blocked, o.get('details_json') if isinstance(o, dict) else None)\n"
        f"{indent}verdict = 'PASS' if passed else f'BLOCK - {{_short_r}}'  "
        f"{MARKER}"
    )
    new_src = new_src.replace(old_line, replacement, 1)

    # 3. Validation AST + py_compile
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        fail(f"AST fail: {e}")

    # ecrire UTF-8 sans BOM
    TARGET.write_text(new_src, encoding="utf-8")

    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as e:
        # rollback
        shutil.copyfile(bak, TARGET)
        fail(f"py_compile fail: {e} - rollback effectue")

    # 4. Verification : marker present, 1 fois
    final = TARGET.read_text(encoding="utf-8-sig")
    n = final.count(MARKER)
    print(f"[OK] marker {MARKER} -> {n} occurrence(s)")
    print(f"[OK] patch applique: {TARGET}")
    print()
    print("Verification rapide :")
    print(f"  - helper _humanize_block_reason inseré")
    print(f"  - verdict 'BLOCK ({{blocked}})' remplace par 'BLOCK - {{libelle_humain}}'")
    print(f"  - backup conservé : {bak.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
