"""
Diag : dump du corps de run_backtest dans backtest_engine.py pour comprendre
la boucle de rebalance et identifier ou injecter les multiplicateurs de regime.
ASCII pur.
"""
import io, os

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
PATH = os.path.join(ROOT, "backtest_engine.py")

with io.open(PATH, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

lines = src.splitlines()
print("=" * 70)
print("DIAG run_backtest BODY (backtest_engine.py)")
print(f"Total: {len(lines)} lignes")
print("=" * 70)

# Dump L100-295 (run_backtest + _compute_stats debut)
print("\n[A] run_backtest body (L100-295)")
for i in range(99, min(295, len(lines))):
    print(f"  L{i+1:4d}: {lines[i].rstrip()[:170]}")

print("\n[B] _compute_stats (L291-360)")
for i in range(290, min(360, len(lines))):
    print(f"  L{i+1:4d}: {lines[i].rstrip()[:170]}")

print("\nDONE")
