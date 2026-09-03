"""
Diag du moteur backtest principal : structure complete, parametres, sortie.
ASCII pur.
"""
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def rd(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

candidates = []
for f in sorted(os.listdir(ROOT)):
    if "backtest" in f.lower() and f.endswith(".py"):
        full = os.path.join(ROOT, f)
        try:
            src = rd(full)
            candidates.append((f, full, src))
        except Exception:
            pass

# Le plus volumineux est probablement le moteur principal
candidates.sort(key=lambda x: -len(x[2]))

print("=" * 70)
print("DIAG BACKTEST ENGINE (top 2 candidats par taille)")
print("=" * 70)

for f, full, src in candidates[:2]:
    print(f"\n=== {f} ({len(src.splitlines())} lignes) ===")
    lines = src.splitlines()

    # Imports
    print("\n[Imports]")
    for i, ln in enumerate(lines[:60], 1):
        s = ln.strip()
        if s.startswith("from ") or s.startswith("import "):
            print(f"  L{i}: {s[:140]}")

    # Defs
    print("\n[Definitions]")
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if s.startswith("def ") or s.startswith("class ") or s.startswith("async def "):
            print(f"  L{i}: {s[:140]}")

    # Cherche entry point: fonction qui boucle sur dates / dataframe
    print("\n[Mots-cles cle : equity, sharpe, drawdown, regime, multiplier]")
    for kw in ["equity_curve", "sharpe", "max_drawdown", "regime", "multiplier", "mult", "rebalance", "dataframe"]:
        cnt = sum(1 for ln in lines if kw.lower() in ln.lower())
        if cnt > 0:
            print(f"  '{kw}': {cnt} occurrences")

    # Signature de la fonction principale (souvent run_backtest)
    print("\n[Signatures probables d'entry point]")
    for i, ln in enumerate(lines, 1):
        if re.match(r"^\s*(async\s+)?def\s+(run_backtest|backtest|do_backtest|execute_backtest|run)\b", ln):
            # imprimer 5 lignes de contexte
            end = min(i + 4, len(lines))
            for j in range(i - 1, end):
                print(f"  L{j+1}: {lines[j].rstrip()[:140]}")
            print("  ...")

print("\nDONE")
