"""
[MEMO_VERDICT_REASON_FIX_V1]

Probleme :
  Le memo IC affiche "BLOCK (broker_mapping_ok)" dans le panneau
  Pre-trade Controls [RISK_V2]. C'est le NOM DU CHECK, pas le motif.
  Le vrai motif est dans details_json[blocked_by]["reason"]
  (par ex. "not_tradable_strict_refusal").

Fix :
  Dans memo_generator.py, fonction _build_risk_v2_section (L260) :
    - injecte une helper _humanize_block_reason() qui mappe technique -> humain FR
    - remplace 'BLOCK ({blocked})' par 'BLOCK - {short_reason_humain}'

Idempotent : marker [MEMO_VERDICT_REASON_FIX_V1].
Backup .py.bak.<timestamp> conserve.

Cibles :
  C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\memo_generator.py
"""
from __future__ import annotations
import ast
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

# Helper Python comme STRING brute (pas de .format pour eviter les {} JSON)
# On garde un dict litteral propre, indentation 4 espaces
HELPER_BLOCK_LINES = [
    "",
    "# " + MARKER,
    "# Traduit un (blocked_by, details_json) en libelle humain court pour le memo IC.",
    "# blocked_by est le NOM DU CHECK (ex: \"broker_mapping_ok\"), pas un motif.",
    "# Le vrai motif se trouve dans details_json[blocked_by][\"reason\"].",
    "def _humanize_block_reason(blocked_by, details_json):",
    "    \"\"\"Returns (short_reason_FR, long_reason_FR) for memo display.\"\"\"",
    "    import json as _json",
    "    try:",
    "        details = _json.loads(details_json) if isinstance(details_json, str) else (details_json or {})",
    "    except Exception:",
    "        details = {}",
    "    sub = (details or {}).get(blocked_by) or {}",
    "    raw_reason = sub.get(\"reason\") or blocked_by or \"unknown\"",
    "    HUMAN = {",
    "        \"not_tradable_strict_refusal\":   (\"Non tradable (regle A)\",",
    "                                          \"Symbole non mappe chez le broker - refus strict\"),",
    "        \"broker_mapping_ok\":             (\"Mapping broker OK\",",
    "                                          \"Verification du mapping broker reussie\"),",
    "        \"concentration_exceeded\":        (\"Concentration > 15%\",",
    "                                          \"Position depasserait le plafond de concentration\"),",
    "        \"var_budget_exceeded\":           (\"Budget VaR depasse\",",
    "                                          \"L'ordre depasse le budget VaR portefeuille\"),",
    "        \"correlation_excess\":            (\"Correlation trop forte\",",
    "                                          \"Correlation 60j > seuil avec autres positions\"),",
    "        \"qty_overshoot\":                 (\"Qty > position\",",
    "                                          \"Quantite SELL superieure a la position detenue\"),",
    "        \"no_position\":                   (\"Aucune position\",",
    "                                          \"Aucune position a vendre pour ce ticker\"),",
    "        \"market_closed\":                 (\"Marche ferme\",",
    "                                          \"Hors plage horaire ou jour ferie NYSE\"),",
    "    }",
    "    short, long_ = HUMAN.get(raw_reason, (raw_reason, raw_reason))",
    "    return short, long_",
    "",
    "",
]
HELPER_BLOCK = "\n".join(HELPER_BLOCK_LINES)


def fail(msg):
    print("[ERR] " + msg)
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail("introuvable: " + str(TARGET))

    src = TARGET.read_text(encoding="utf-8-sig")

    if MARKER in src:
        print("[SKIP] " + MARKER + " deja present dans memo_generator.py")
        return 0

    bak = TARGET.with_suffix(
        ".py.bak." + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    shutil.copyfile(TARGET, bak)
    print("[OK] backup -> " + bak.name)

    # 1. Inserer le helper AVANT 'def _build_risk_v2_section'
    pat_helper = re.compile(r"^def\s+_build_risk_v2_section\s*\(", re.MULTILINE)
    m = pat_helper.search(src)
    if not m:
        fail("def _build_risk_v2_section introuvable dans memo_generator.py")
    new_src = src[: m.start()] + HELPER_BLOCK + src[m.start() :]

    # 2. Remplacer la ligne verdict
    # forme exacte attendue (L260) :
    #     verdict = "PASS" if passed else f"BLOCK ({blocked})"
    pat_verdict = re.compile(
        r'(\s*)verdict\s*=\s*"PASS"\s+if\s+passed\s+else\s+f"BLOCK\s*\(\{blocked\}\)"'
    )
    m2 = pat_verdict.search(new_src)
    if not m2:
        # Variante tolerante
        pat2 = re.compile(
            r'(\s*)verdict\s*=\s*"PASS"\s+if\s+passed\s+else\s+f"BLOCK[^"]*"'
        )
        m2 = pat2.search(new_src)
        if not m2:
            shutil.copyfile(bak, TARGET)
            fail("ligne 'verdict = ... BLOCK' introuvable - rollback")

    indent = m2.group(1) or "            "
    old_line = m2.group(0)

    replacement_lines = [
        indent + "# " + MARKER,
        indent + "_details_for_humanize = o.get(\"details_json\") if isinstance(o, dict) else None",
        indent + "if _details_for_humanize is None:",
        indent + "    try:",
        indent + "        _details_for_humanize = row.get(\"details_json\") if isinstance(row, dict) else row[\"details_json\"]",
        indent + "    except Exception:",
        indent + "        _details_for_humanize = None",
        indent + "_short_r, _long_r = _humanize_block_reason(blocked, _details_for_humanize)",
        indent + "verdict = \"PASS\" if passed else (\"BLOCK - \" + _short_r)",
    ]
    replacement = "\n".join(replacement_lines)

    new_src = new_src.replace(old_line, "\n" + replacement, 1)

    # 3. Validation AST
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        shutil.copyfile(bak, TARGET)
        fail("AST fail: " + str(e) + " - rollback effectue")

    # ecrire UTF-8 sans BOM
    TARGET.write_text(new_src, encoding="utf-8")

    # 4. py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as e:
        shutil.copyfile(bak, TARGET)
        fail("py_compile fail: " + str(e) + " - rollback effectue")

    # 5. Verifications
    final = TARGET.read_text(encoding="utf-8-sig")
    n = final.count(MARKER)
    print("[OK] marker " + MARKER + " -> " + str(n) + " occurrence(s)")
    print("[OK] _humanize_block_reason : " + str(final.count("def _humanize_block_reason")) + " definition(s)")
    print("[OK] patch applique : " + str(TARGET))
    print("[OK] backup conserve : " + bak.name)
    print()
    print("Verification rapide :")
    print("  - helper _humanize_block_reason insere avant _build_risk_v2_section")
    print("  - verdict 'BLOCK ({blocked})' remplace par 'BLOCK - <libelle FR humain>'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
