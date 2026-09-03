"""Validation post-patch : verifie injection SHADOW_HOOK_V1 dans api_server.py.

1. Marker [SHADOW_HOOK_V1] BEGIN present
2. Bloc bien positionne entre /[HISTORY_SNAPSHOT_V1] et return
3. shadow_hook importable
4. Affiche le bloc injecte (L880-L915)
"""
import os, sys, ast

FPATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, ROOT)

with open(FPATH, "rb") as f:
    src = f.read().decode("utf-8-sig", errors="replace")

print("=== 1. Marker present ===")
print(f"  [SHADOW_HOOK_V1] BEGIN : count={src.count('[SHADOW_HOOK_V1] BEGIN')}")
print(f"  [SHADOW_HOOK_V1] END   : count={src.count('[SHADOW_HOOK_V1] END')}")
print(f"  shadow_hook import     : count={src.count('import shadow_hook')}")

print("\n=== 2. Bloc autour du SHADOW_HOOK_V1 ===")
lines = src.split("\n")
for i, ln in enumerate(lines, 1):
    if "[SHADOW_HOOK_V1] BEGIN" in ln:
        # Print 16 lines around
        for j in range(max(0, i-3), min(len(lines), i+15)):
            print(f"  L{j+1:4d}: {lines[j]}")
        break

print("\n=== 3. AST parse api_server.py ===")
try:
    ast.parse(src)
    print("  OK")
except SyntaxError as e:
    print(f"  FAIL: {e}")

print("\n=== 4. shadow_hook importable ===")
try:
    import shadow_hook
    print(f"  OK : module @ {shadow_hook.__file__}")
    print(f"  run_shadow_cycle present : {hasattr(shadow_hook, 'run_shadow_cycle')}")
except Exception as e:
    print(f"  FAIL : {e}")
