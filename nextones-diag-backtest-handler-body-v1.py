"""
Diag : corps du handler POST /api/backtest dans api_server.py + lien
api_server_with_static.py -> api_server.py (import / mount).
ASCII pur.
"""
import io, os

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def rd(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

print("=" * 70)
print("DIAG BACKTEST HANDLER BODY")
print("=" * 70)

# A) Comment api_server_with_static.py reference-t-il api_server.py ?
api_static = os.path.join(ROOT, "api_server_with_static.py")
src_static = rd(api_static)
print("\n[A] api_server_with_static.py : refs a api_server")
for i, ln in enumerate(src_static.splitlines(), 1):
    if "api_server" in ln and "with_static" not in ln:
        print(f"  L{i}: {ln.rstrip()[:160]}")

# B) Corps de POST /api/backtest dans api_server.py (L2765)
api = os.path.join(ROOT, "api_server.py")
src = rd(api)
lines = src.splitlines()

print("\n[B] POST /api/backtest L2765-2830 (handler complet)")
for i in range(2762, min(2830, len(lines))):
    print(f"  L{i+1:4d}: {lines[i].rstrip()[:170]}")

print("\n[C] POST /api/backtest/export-csv L2827-2895")
for i in range(2824, min(2895, len(lines))):
    print(f"  L{i+1:4d}: {lines[i].rstrip()[:170]}")

print("\n[D] GET /api/backtest/presets L2889-end")
for i in range(2886, min(2960, len(lines))):
    print(f"  L{i+1:4d}: {lines[i].rstrip()[:170]}")

# E) Recherche specifique du modele Pydantic / Body utilise
print("\n[E] Modeles Pydantic / Body pour backtest")
import re
for i, ln in enumerate(lines, 1):
    s = ln.strip()
    if ("class " in s and ("Backtest" in s or "BacktestReq" in s or "BacktestParams" in s)):
        end = min(i + 12, len(lines))
        for j in range(i - 1, end):
            print(f"  L{j+1}: {lines[j].rstrip()[:170]}")
        print("  ...")

print("\nDONE")
