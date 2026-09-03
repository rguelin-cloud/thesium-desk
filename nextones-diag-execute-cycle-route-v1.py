"""Trouve la decoration FastAPI exacte de execute_cycle."""
FPATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
with open(FPATH, "rb") as f:
    src = f.read().decode("utf-8-sig", errors="replace")
lines = src.split("\n")
# Trouve "def execute_cycle"
for i, ln in enumerate(lines, 1):
    if "def execute_cycle" in ln:
        # Affiche 10 lignes au-dessus pour voir les decorateurs
        for j in range(max(0, i-10), i+1):
            print(f"  L{j+1:4d}: {lines[j]}")
        break
