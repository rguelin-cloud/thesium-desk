"""
[SMOOTHING_FORCED_EXIT_BYPASS_V1]

BUG: smooth_vs_previous applique le clamp +/-2.0%/cycle sans tenir compte
     de forced_exit -> AAPL passe de 3.7382 a 1.7382 au lieu de 0,
     SOL passe de 2.771 a 0.771 au lieu de 0.

FIX:
  1. Etendre la signature de smooth_vs_previous pour accepter un dict
     'force_zero_tickers' (set/dict avec valeur truthy).
  2. Si ticker dedans -> ecrire 0.0 SANS clamp.
  3. Au callsite (L1041), passer les tickers avec forced_exit=1 ou
     sizing_multiplier==0 depuis conv_log.

Cible : portfolio_construction_agent_jalon2.py
Markers : [SMOOTHING_FORCED_EXIT_BYPASS_V1]
Idempotent : skip si marker present.
ASCII pur, AST + py_compile valides, backup .bak.<ts>.
"""
import os
import re
import sys
import ast
import time
import shutil
import py_compile

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "portfolio_construction_agent_jalon2.py")
MARKER = "[SMOOTHING_FORCED_EXIT_BYPASS_V1]"


def main():
    if not os.path.isfile(TARGET):
        print("[ERR] target not found : " + TARGET)
        sys.exit(2)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[SKIP] marker already present : " + MARKER)
        return

    # ===== PATCH 1 : signature + corps de smooth_vs_previous =====
    # On cherche la signature exacte. Diag dit :
    # L743: max_delta_pct: float) -> dict:
    # L749: smoothed = {}
    # On va remplacer le bloc complet en gardant la logique.

    # Pattern : trouver "def smooth_vs_previous"
    # Approche robuste : remplacer la fonction entiere par regex
    fn_pattern = re.compile(
        r"(def smooth_vs_previous\([^)]*\)\s*->\s*dict:\s*\n"
        r'(?:\s*"""[\s\S]*?"""\s*\n)?'  # optional docstring
        r")(.*?)(?=\n(?:def |class |# ====|if __name__))",
        re.DOTALL,
    )

    m = fn_pattern.search(src)
    if not m:
        print("[ERR] smooth_vs_previous function not found via regex")
        sys.exit(3)

    # Reconstruire la fonction avec le bypass
    # On garde la signature originale + on ajoute un parametre optionnel
    # On enrobe via une nouvelle version qui prend force_zero_tickers
    original_header = m.group(1)

    # Modifier la signature pour ajouter force_zero_tickers=None
    # Header peut etre multiligne, on cherche la 1ere ")" suivie de "->"
    # Plus simple : on insere un nouveau parametre avant le " ->"
    if "force_zero_tickers" in original_header:
        print("[SKIP] smooth_vs_previous deja patche (force_zero_tickers present)")
        return

    new_header = original_header.replace(
        "max_delta_pct: float) -> dict:",
        "max_delta_pct: float, force_zero_tickers=None) -> dict:",
        1,
    )
    if new_header == original_header:
        print("[ERR] failed to update smooth_vs_previous signature")
        print("[DEBUG] header was:")
        print(original_header)
        sys.exit(4)

    new_body = (
        "    # " + MARKER + " : bypass smoothing pour forced_exit\n"
        "    if force_zero_tickers is None:\n"
        "        force_zero_tickers = set()\n"
        "    smoothed = {}\n"
        "    for ticker, new_w in new_alloc.items():\n"
        "        if ticker in force_zero_tickers:\n"
        "            # forced_exit ou sizing_multiplier=0 -> ecriture directe a 0\n"
        "            smoothed[ticker] = 0.0\n"
        "            continue\n"
        "        prev_w = prev.get(ticker, 0.0)\n"
        "        delta = new_w - prev_w\n"
        "        if abs(delta) > max_delta_pct:\n"
        "            smoothed[ticker] = prev_w + math.copysign(max_delta_pct, delta)\n"
        "        else:\n"
        "            smoothed[ticker] = new_w\n"
        "    return smoothed\n"
    )

    src_patched = src[:m.start()] + new_header + new_body + src[m.end():]

    # ===== PATCH 2 : callsite L1041 =====
    # Trouver l'appel a smooth_vs_previous et passer force_zero_tickers
    callsite_pattern = re.compile(
        r"(\n    smoothed = smooth_vs_previous\(\n"
        r"        capped_alloc, prev_agent_targets,\n"
        r"        float\(config\[\"smoothing_max_delta_pct\"\]\)\n"
        r"    \))"
    )

    m2 = callsite_pattern.search(src_patched)
    if not m2:
        print("[ERR] callsite smooth_vs_previous not found")
        # Fallback : pattern plus tolerant
        alt = re.search(
            r"smoothed = smooth_vs_previous\(\s*"
            r"capped_alloc,\s*prev_agent_targets,\s*"
            r"float\(config\[\"smoothing_max_delta_pct\"\]\)\s*\)",
            src_patched,
        )
        if not alt:
            print("[ERR] callsite introuvable meme avec pattern tolerant")
            sys.exit(5)
        print("[INFO] callsite trouve via pattern tolerant")
        # Construire le remplacement
        prefix = (
            "_force_zero = {  # " + MARKER + "\n"
            "        _t for _t, _meta in conv_log.items()\n"
            "        if (len(_meta) >= 3 and _meta[2] == 1) or "
            "(len(_meta) >= 1 and float(_meta[0] or 1.0) == 0.0)\n"
            "    }\n"
            "    smoothed = smooth_vs_previous(\n"
            "        capped_alloc, prev_agent_targets,\n"
            "        float(config[\"smoothing_max_delta_pct\"]),\n"
            "        force_zero_tickers=_force_zero,\n"
            "    )"
        )
        src_patched = src_patched.replace(alt.group(0), prefix, 1)
    else:
        # Reconstruction propre
        new_call = (
            "\n    # " + MARKER + " : tickers forced_exit/mult=0 -> bypass smoothing\n"
            "    _force_zero = {\n"
            "        _t for _t, _meta in conv_log.items()\n"
            "        if (len(_meta) >= 3 and _meta[2] == 1) or "
            "(len(_meta) >= 1 and float(_meta[0] or 1.0) == 0.0)\n"
            "    }\n"
            "    smoothed = smooth_vs_previous(\n"
            "        capped_alloc, prev_agent_targets,\n"
            "        float(config[\"smoothing_max_delta_pct\"]),\n"
            "        force_zero_tickers=_force_zero,\n"
            "    )"
        )
        src_patched = src_patched[:m2.start()] + new_call + src_patched[m2.end():]

    # Validation AST
    try:
        ast.parse(src_patched)
    except SyntaxError as e:
        print("[ERR] AST parse failed : " + str(e))
        # Dump du contexte pour debug
        lines = src_patched.split("\n")
        ln = e.lineno or 1
        start = max(0, ln - 5)
        end = min(len(lines), ln + 5)
        for i in range(start, end):
            mark = ">>" if (i + 1) == ln else "  "
            print("  {} L{}: {}".format(mark, i + 1, lines[i]))
        sys.exit(6)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP] " + bak)

    # Ecriture
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(src_patched)

    # py_compile
    try:
        py_compile.compile(TARGET, doraise=True)
    except py_compile.PyCompileError as e:
        print("[ERR] py_compile failed : " + str(e))
        print("[ROLLBACK]")
        shutil.copy2(bak, TARGET)
        sys.exit(7)

    # Verifier que le marker est bien la 2 fois (function + callsite)
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        verify = f.read()
    n_marker = verify.count(MARKER)
    print("[VERIFY] marker '" + MARKER + "' present {} fois".format(n_marker))
    if n_marker < 2:
        print("[WARN] marker manquant - verifier manuellement")

    print("[OK] patch applique")
    print("[NEXT]")
    print("  Get-NetTCPConnection -LocalPort 8000 | "
          "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
    print("  Start-Sleep -Seconds 2")
    print("  Start-Process powershell -ArgumentList '-NoExit','-Command'"
          ",'cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk; "
          "py -3.13 -m uvicorn api_server_with_static:app "
          "--host 0.0.0.0 --port 8000'")
    print("  Start-Sleep -Seconds 6")
    print("  powershell -ExecutionPolicy Bypass -File "
          ".\\nextones-run-full-cycle-and-verify-v2.ps1")


if __name__ == "__main__":
    main()
