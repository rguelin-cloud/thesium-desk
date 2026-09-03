# -*- coding: utf-8 -*-
# nextones-fix-convergence-refresh-per-cycle-v1.py
# Marker : [CONVERGENCE_REFRESH_PER_CYCLE_V1]
#
# Insere dans execution_engine.run_decision_cycle un appel a
# convergence_engine.compute_convergence + save_convergence_snapshot
# APRES run_exit_agent (qui produit les ExitAgent rows) et AVANT le Reconciler
# (et donc avant create_and_execute_order -> RISK_V2 -> garde-fou).
#
# Strategie :
#  1. Ajout (en local dans la fonction) d'un try/except qui :
#     - importe convergence_engine
#     - appelle compute_convergence(conn, cycle_id)
#     - appelle save_convergence_snapshot(conn, cycle_id, results)
#     - commit
#     - print resume
#  2. Ancre : ligne contenant "[exit_agent] ERREUR (non bloquant)" puis chercher
#     le 'traceback.print_exc()' suivant -> on insere apres le except complet.
#  3. Validation : marker presence + AST + py_compile
#  4. Backup .bak.<timestamp>

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(PROD, "execution_engine.py")
MARKER = "[CONVERGENCE_REFRESH_PER_CYCLE_V1]"

print()
print("=" * 72)
print("PATCH : refresh convergence_snapshots a chaque run_decision_cycle")
print("-" * 72)

with open(EE, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

if MARKER in content:
    print("  [SKIP] Marker deja present")
    sys.exit(0)

lines = content.split("\n")

# --- Trouver le bloc except qui suit run_exit_agent
# Ancre : ligne contenant "[exit_agent] ERREUR"
anchor_idx = None
for i, line in enumerate(lines):
    if "[exit_agent] ERREUR" in line:
        anchor_idx = i
        break

if anchor_idx is None:
    print("  [KO] Ancre '[exit_agent] ERREUR' introuvable")
    sys.exit(2)

print("  Ancre trouvee L%d : %s" % (anchor_idx + 1, lines[anchor_idx].strip()[:120]))

# Trouver le traceback.print_exc() apres l'ancre
insert_after = None
for j in range(anchor_idx + 1, min(len(lines), anchor_idx + 10)):
    if "traceback.print_exc" in lines[j]:
        insert_after = j
        break

if insert_after is None:
    print("  [KO] 'traceback.print_exc' apres ancre introuvable")
    sys.exit(3)

print("  Insertion apres L%d : %s" % (insert_after + 1, lines[insert_after].strip()[:120]))

# --- Indentation : on prend l'indent du traceback (4 espaces normalement dans le try/except)
ref_line = lines[insert_after]
indent = ref_line[:len(ref_line) - len(ref_line.lstrip())]
# L'insertion doit etre au meme niveau que le 'try:' parent, donc on remonte l'indent
# Cherchons le 'try:' qui ouvre le bloc exit_agent
try_idx = None
for k in range(anchor_idx, max(0, anchor_idx - 20), -1):
    s = lines[k].lstrip()
    if s.startswith("try:") and "run_exit_agent" in "\n".join(lines[k:k+5]):
        try_idx = k
        break

if try_idx is None:
    # fallback : indent du except
    for k in range(anchor_idx, max(0, anchor_idx - 5), -1):
        s = lines[k].lstrip()
        if s.startswith("except "):
            ref = lines[k]
            outer_indent = ref[:len(ref) - len(ref.lstrip())]
            break
    else:
        outer_indent = "    "
else:
    ref = lines[try_idx]
    outer_indent = ref[:len(ref) - len(ref.lstrip())]
    print("  try parent L%d trouve, indent='%s' (%d sp)" % (try_idx + 1, repr(outer_indent), len(outer_indent)))

print("  Indent niveau bloc : %d espaces" % len(outer_indent))

# --- Construire le bloc a inserer (TOUT comme statements au meme niveau)
# IMPORTANT : pas de commentaire inline dans une expression multi-lignes
block_lines = [
    "",
    outer_indent + "# " + MARKER + " - refresh convergence_snapshots a chaque cycle",
    outer_indent + "try:",
    outer_indent + "    from convergence_engine import compute_convergence as _conv_compute",
    outer_indent + "    from convergence_engine import save_convergence_snapshot as _conv_save",
    outer_indent + "    _conv_results = _conv_compute(conn, cycle_id)",
    outer_indent + "    _conv_n = _conv_save(conn, cycle_id, _conv_results)",
    outer_indent + "    conn.commit()",
    outer_indent + "    _conv_forced = sum(1 for _r in _conv_results if _r.get('forced_exit'))",
    outer_indent + "    print(f\"[convergence] cycle_id={cycle_id} tickers={_conv_n} forced_exit={_conv_forced}\")",
    outer_indent + "except Exception as _ce:",
    outer_indent + "    import traceback as _ctb",
    outer_indent + "    print(f\"[convergence] ERREUR refresh (non bloquant) : {_ce}\")",
    outer_indent + "    _ctb.print_exc()",
]

# --- Insertion : on insere apres la ligne traceback.print_exc()
# Donc on insere a l'index insert_after + 1
new_lines = lines[:insert_after + 1] + block_lines + lines[insert_after + 1:]
new_content = "\n".join(new_lines)

# --- Validation AST
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST : %s" % e)
    # Dump 10 lignes autour de l'erreur pour debug
    if hasattr(e, "lineno"):
        for k in range(max(0, e.lineno - 5), min(len(new_lines), e.lineno + 5)):
            print("    L%d: %s" % (k + 1, new_lines[k][:160].rstrip()))
    sys.exit(4)

# --- Backup + ecriture
ts = time.strftime("%Y%m%d_%H%M%S")
bak = EE + ".bak." + ts
shutil.copy2(EE, bak)
print("  Backup : %s" % os.path.basename(bak))

with open(EE, "w", encoding="utf-8", newline="") as fh:
    fh.write(new_content)

try:
    py_compile.compile(EE, doraise=True)
    print("  py_compile OK")
except py_compile.PyCompileError as e:
    shutil.copy2(bak, EE)
    print("  [KO] py_compile : %s -- restore" % e)
    sys.exit(5)

print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  Insertion %d lignes apres L%d (post traceback exit_agent)" % (len(block_lines), insert_after + 1))
print("  Bloc :")
for bl in block_lines:
    print("    | %s" % bl.rstrip())
print()
print("  Validation :")
print("    1. Restart API :")
print("       Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }")
print("       Start-Sleep 2")
print("       Start-Process powershell -ArgumentList '-NoExit','-Command','cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk; py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000'")
print("    2. Cycle reel :")
print("       powershell -ExecutionPolicy Bypass -File .\\nextones-run-execute-cycle-auth.ps1")
print("    3. Validation :")
print("       py -3.13 .\\nextones-validate-convergence-block-prod-v2.py")
print("       -> on doit voir un nouveau cycle_id (20260610-xxxxxx) dans convergence_snapshots")
print("=" * 72)
