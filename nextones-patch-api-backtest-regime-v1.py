"""
[PATCH_API_BACKTEST_REGIME_V1]
Patche api_server.py pour propager apply_regime au moteur backtest.

A) Ajoute champ apply_regime: bool = False au modele Pydantic BacktestRequest.
B) Passe apply_regime=req.apply_regime a backtest_engine.run_backtest(...).

Idempotent, backup .py.bak.<timestamp>, validation ast.parse + py_compile.
ASCII pur strict.
"""
import io
import os
import sys
import ast
import py_compile
import shutil
import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
MARKER = "[PATCH_API_BACKTEST_REGIME_V1]"


def read_utf8_sig(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="strict") as f:
        return f.read()


def write_utf8_no_bom(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def assert_ascii(snippet, label):
    bad = [(i, b) for i, b in enumerate(snippet.encode("utf-8")) if b > 127]
    if bad:
        raise RuntimeError(
            "Snippet %s contient %d bytes non-ASCII (premier @ offset %d byte=%d)"
            % (label, len(bad), bad[0][0], bad[0][1])
        )


def main():
    print("=" * 70)
    print("PATCH api_server.py - BACKTEST REGIME V1")
    print("=" * 70)

    if not os.path.exists(TARGET):
        print("[FAIL] introuvable: " + TARGET)
        sys.exit(1)

    src = read_utf8_sig(TARGET)
    if MARKER in src:
        print("[SKIP] marker deja present " + MARKER)
        return

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP] " + bak)

    lines = src.splitlines(keepends=False)

    # ---- A) Ajouter apply_regime au modele BacktestRequest ----
    # Cible : la ligne 'custom_weights: dict[str, float] | None = None'
    # On insere apres celle-ci, dans la classe BacktestRequest.
    inject_a_idx = None
    in_model = False
    for i, ln in enumerate(lines):
        if ln.startswith("class BacktestRequest("):
            in_model = True
            continue
        if in_model:
            if ln.startswith("class ") and "BacktestRequest" not in ln:
                # quitte la classe sans avoir trouve la cible
                break
            if "custom_weights" in ln and ": dict" in ln:
                inject_a_idx = i + 1
                break

    if inject_a_idx is None:
        print("[FAIL] champ custom_weights dans BacktestRequest introuvable")
        sys.exit(2)

    snippet_a = "    apply_regime: bool = False  # " + MARKER
    assert_ascii(snippet_a, "field apply_regime")
    lines.insert(inject_a_idx, snippet_a)
    print("[INJECT] champ apply_regime dans BacktestRequest (apres L%d)" % inject_a_idx)

    # ---- B) Passer apply_regime au moteur dans run_backtest_endpoint ----
    # On cherche la ligne "benchmark=req.benchmark," et on insere apres
    inject_b_idx = None
    # On recommence depuis le debut pour eviter le decalage de l'inject_a
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s == "benchmark=req.benchmark,":
            # verifier qu'on est dans le bloc run_backtest_endpoint (regard arriere ~50 lignes)
            ctx_start = max(0, i - 60)
            ctx = "\n".join(lines[ctx_start:i])
            if "backtest_engine.run_backtest(" in ctx:
                inject_b_idx = i + 1
                break

    if inject_b_idx is None:
        print("[FAIL] appel a backtest_engine.run_backtest(...) introuvable")
        sys.exit(3)

    # Detecte l'indentation de la ligne 'benchmark=req.benchmark,' pour matcher exactement
    ref_line = lines[inject_b_idx - 1]
    indent_b = ref_line[: len(ref_line) - len(ref_line.lstrip())]
    snippet_b = indent_b + "apply_regime=req.apply_regime,  # " + MARKER
    assert_ascii(snippet_b, "arg apply_regime")
    lines.insert(inject_b_idx, snippet_b)
    print("[INJECT] arg apply_regime dans run_backtest_endpoint (apres L%d)" % inject_b_idx)

    new_src = "\n".join(lines) + "\n"

    # ---- VALIDATION ----
    try:
        ast.parse(new_src)
        print("[VALIDATE] ast.parse OK")
    except SyntaxError as e:
        print("[FAIL] ast.parse: %s" % e)
        sys.exit(10)

    tmp = TARGET + ".tmp"
    write_utf8_no_bom(tmp, new_src)
    try:
        py_compile.compile(tmp, doraise=True)
        print("[VALIDATE] py_compile OK")
    except py_compile.PyCompileError as e:
        print("[FAIL] py_compile: %s" % e)
        os.remove(tmp)
        sys.exit(11)

    os.replace(tmp, TARGET)
    print("[WRITE] %s" % TARGET)
    print("[OK] " + MARKER)


if __name__ == "__main__":
    main()
