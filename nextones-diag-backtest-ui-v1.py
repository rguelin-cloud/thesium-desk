"""
Diag UI backtest : extrait tab-backtest HTML + handlers JS.
ASCII pur.
"""
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def rd(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

print("=" * 70)
print("DIAG BACKTEST UI")
print("=" * 70)

# A) HTML : extraire la section tab-backtest complete
idx = os.path.join(ROOT, "index.html")
if os.path.exists(idx):
    src = rd(idx)
    lines = src.splitlines()
    m = re.search(r'<section[^>]*id="tab-backtest"[^>]*>', src)
    if m:
        start_line = src[:m.start()].count("\n")
        # cherche la fermeture: prochaine ouverture de <section ou fin
        depth = 0
        end_line = start_line
        for i in range(start_line, len(lines)):
            ln = lines[i]
            depth += ln.count("<section")
            depth -= ln.count("</section>")
            if depth <= 0:
                end_line = i
                break
        print(f"\n[A] HTML tab-backtest L{start_line+1} -> L{end_line+1}")
        for i in range(start_line, end_line + 1):
            print(f"  L{i+1}: {lines[i].rstrip()[:160]}")

# B) JS : chercher dans app.js les handlers backtest
appjs = os.path.join(ROOT, "app.js")
if os.path.exists(appjs):
    src = rd(appjs)
    lines = src.splitlines()
    print(f"\n[B] app.js : occurrences backtest (cle)")
    keywords = ["backtest", "Backtest", "lancerBacktest", "runBacktest", "btnBacktest", "btn-backtest", "tab-backtest"]
    seen_lines = set()
    for i, ln in enumerate(lines, 1):
        for kw in keywords:
            if kw in ln:
                if i not in seen_lines:
                    print(f"  L{i}: {ln.rstrip()[:160]}")
                    seen_lines.add(i)
                break

    # Chercher fonction principale
    print("\n[C] Fonctions JS *backtest*")
    for i, ln in enumerate(lines, 1):
        s = ln.strip()
        if ("function" in s or "=>" in s or "async" in s) and "backtest" in s.lower():
            print(f"  L{i}: {s[:160]}")

print("\nDONE")
