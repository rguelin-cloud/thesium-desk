# diag_reset_insert_history.py
# Trouver l'INSERT INTO portfolio_history qui plante au reset
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

root = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# Recherche multi-lignes : INSERT INTO portfolio_history dans n'importe quel fichier
print("=" * 70)
print("Recherche INSERT INTO portfolio_history (Python + PowerShell + SQL)")
print("=" * 70)

extensions = ["*.py", "*.ps1", "*.sql"]
all_files = []
for ext in extensions:
    all_files.extend(root.glob(ext))

# Inclure aussi sous-dossiers immediats (1 niveau)
for ext in extensions:
    all_files.extend(root.glob(f"*/{ext}"))

for f in all_files:
    if "_backups" in str(f) or "node_modules" in str(f):
        continue
    try:
        content = f.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    
    # Recherche directe "INSERT INTO portfolio_history"
    if "portfolio_history" in content.lower():
        lines = content.split("\n")
        # Trouver toutes occurrences
        for i, line in enumerate(lines):
            if "portfolio_history" in line.lower():
                # Voir si INSERT est dans les 5 lignes precedentes ou la ligne courante
                ctx_window = lines[max(0,i-5):i+10]
                ctx_text = "\n".join(ctx_window)
                if "INSERT" in ctx_text.upper() or "insert" in ctx_text:
                    rel = f.relative_to(root)
                    print(f"\n--- {rel} L{i+1} ---")
                    for j in range(max(0,i-5), min(len(lines), i+10)):
                        marker = ">>> " if j == i else "    "
                        print(f"  L{j+1:5d}{marker}{lines[j].rstrip()[:140]}")
                    break  # une seule occurrence par fichier suffit pour le diag
