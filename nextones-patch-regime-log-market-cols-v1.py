# -*- coding: utf-8 -*-
"""
Patch : enrichit l'INSERT INTO regime_log a L468 pour ecrire les
nouvelles colonnes ajoutees par Phase 1 :
  equity_regime, crypto_regime,
  equity_buy_mult, equity_sell_mult,
  crypto_buy_mult, crypto_sell_mult

Lit regime_info['market'] (dict {equity:{...}, crypto:{...}}) et
remplit les colonnes. NULL si market_info absent.

Marker idempotent : [PATCH_REGIME_LOG_MARKET_COLS_V1]
"""
import ast
import os
import py_compile
import re
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(ROOT, "execution_engine.py")
MARKER = "[PATCH_REGIME_LOG_MARKET_COLS_V1]"

# Lecture
with open(EE, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print(f"[SKIP] Marker {MARKER} deja present.")
    sys.exit(0)

lines = src.splitlines(keepends=True)

# Localiser INSERT INTO regime_log
idx_insert = None
for i, line in enumerate(lines):
    if "INSERT INTO regime_log" in line:
        idx_insert = i
        break
if idx_insert is None:
    print("[ERR] INSERT INTO regime_log introuvable")
    sys.exit(1)

# Localiser la ligne 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
idx_values = None
for i in range(idx_insert, min(idx_insert + 10, len(lines))):
    if "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" in lines[i]:
        idx_values = i
        break
if idx_values is None:
    print("[ERR] VALUES (...) avec 11 placeholders introuvable")
    sys.exit(2)

# Localiser la ligne des colonnes (cycle_id, regime, invested_pct, ...)
idx_cols_a = idx_insert + 1  # 'cycle_id, regime, invested_pct, nav, cash, n_positions,'
idx_cols_b = idx_insert + 2  # 'n_proposals_in, n_proposals_attenuated, n_sell_capped, n_buy_capped, notes)'

if "cycle_id" not in lines[idx_cols_a] or "n_proposals_in" not in lines[idx_cols_b]:
    print("[ERR] Lignes de colonnes inattendues")
    print(f"  L{idx_cols_a+1}: {lines[idx_cols_a]!r}")
    print(f"  L{idx_cols_b+1}: {lines[idx_cols_b]!r}")
    sys.exit(3)

# Localiser la ligne 'notes,' (derniere binding)
idx_notes = None
for i in range(idx_values, min(idx_values + 20, len(lines))):
    if re.match(r"\s*notes,\s*$", lines[i]):
        idx_notes = i
        break
if idx_notes is None:
    print("[ERR] Binding 'notes,' introuvable")
    sys.exit(4)

# Localiser la ligne fermante '))' juste apres notes
idx_close = None
for i in range(idx_notes + 1, min(idx_notes + 5, len(lines))):
    if "))" in lines[i]:
        idx_close = i
        break
if idx_close is None:
    print("[ERR] Fermeture '))' introuvable")
    sys.exit(5)

print(f"[OK] Points d'injection :")
print(f"  L{idx_insert+1}  INSERT INTO regime_log")
print(f"  L{idx_cols_a+1}  colonnes ligne A")
print(f"  L{idx_cols_b+1}  colonnes ligne B")
print(f"  L{idx_values+1}  VALUES (...)")
print(f"  L{idx_notes+1}   notes,")
print(f"  L{idx_close+1}   fermeture ))")

# Indentation du binding 'notes,'
indent_b = lines[idx_notes][: len(lines[idx_notes]) - len(lines[idx_notes].lstrip())]

# Modifications (du bas vers le haut pour preserver les indices)
new_lines = list(lines)

# (1) Ajouter les bindings apres 'notes,'
inject_bindings = (
    indent_b + f"# {MARKER} extra columns from regime_info['market']\n"
    + indent_b + "(regime_info.get('market', {}) or {}).get('equity', {}).get('regime') if isinstance(regime_info.get('market'), dict) else None,\n"
    + indent_b + "(regime_info.get('market', {}) or {}).get('crypto', {}).get('regime') if isinstance(regime_info.get('market'), dict) else None,\n"
    + indent_b + "(regime_info.get('market', {}) or {}).get('equity', {}).get('buy_mult') if isinstance(regime_info.get('market'), dict) else None,\n"
    + indent_b + "(regime_info.get('market', {}) or {}).get('equity', {}).get('sell_mult') if isinstance(regime_info.get('market'), dict) else None,\n"
    + indent_b + "(regime_info.get('market', {}) or {}).get('crypto', {}).get('buy_mult') if isinstance(regime_info.get('market'), dict) else None,\n"
    + indent_b + "(regime_info.get('market', {}) or {}).get('crypto', {}).get('sell_mult') if isinstance(regime_info.get('market'), dict) else None,\n"
)
new_lines[idx_notes] = lines[idx_notes] + inject_bindings

# (2) Modifier la ligne VALUES
new_lines[idx_values] = lines[idx_values].replace(
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

# (3) Modifier la ligne des colonnes B pour ajouter les nouvelles colonnes
#     Ligne actuelle :
#     "           n_proposals_in, n_proposals_attenuated, n_sell_capped, n_buy_capped, notes)"
new_lines[idx_cols_b] = lines[idx_cols_b].replace(
    "n_proposals_in, n_proposals_attenuated, n_sell_capped, n_buy_capped, notes)",
    "n_proposals_in, n_proposals_attenuated, n_sell_capped, n_buy_capped, notes,\n"
    + " " * 11
    + "equity_regime, crypto_regime, equity_buy_mult, equity_sell_mult, crypto_buy_mult, crypto_sell_mult)"
)

new_src = "".join(new_lines)

# Validation AST
try:
    ast.parse(new_src)
    print("[OK] ast.parse passed")
except SyntaxError as e:
    print(f"[ERR] SyntaxError: {e}")
    err = new_src.splitlines()
    a = max(0, (e.lineno or 1) - 5)
    b = min(len(err), (e.lineno or 1) + 5)
    for k in range(a, b):
        print(f"  L{k+1:5} | {err[k][:170]}")
    sys.exit(10)

# Backup + ecriture + py_compile
ts = time.strftime("%Y%m%d-%H%M%S")
backup = EE + f".bak.{ts}"
shutil.copyfile(EE, backup)
print(f"[OK] Backup -> {backup}")

with open(EE, "w", encoding="utf-8", newline="") as f:
    f.write(new_src)
print(f"[OK] {EE} reecrit ({new_src.count(chr(10))} lignes)")

try:
    py_compile.compile(EE, doraise=True)
    print("[OK] py_compile passed")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile failed: {e}")
    shutil.copyfile(backup, EE)
    print(f"[ROLLBACK] depuis {backup}")
    sys.exit(11)

# Verifs
with open(EE, "r", encoding="utf-8-sig") as f:
    final = f.read()
print(f"[OK] Marker {MARKER} present x{final.count(MARKER)}")

print()
print("=" * 70)
print("PATCH regime_log enrichi")
print("=" * 70)
print("Maintenant regime_log capture 17 colonnes par cycle :")
print("  +equity_regime, crypto_regime")
print("  +equity_buy_mult, equity_sell_mult")
print("  +crypto_buy_mult, crypto_sell_mult")
print()
print("Au prochain Run Cycle ces colonnes seront remplies si market_info present")
print("(NULL en fallback si l'agent market_regime a echoue)")
