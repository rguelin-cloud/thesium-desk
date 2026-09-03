# -*- coding: utf-8 -*-
"""
[DIAG_API_INSERT] Trouve un point d'insertion propre dans api_server_with_static.py
"""
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"

with open(API, "r", encoding="utf-8-sig") as f:
    content = f.read()
    lines = content.split("\n")

# Restore le backup avant de re-essayer
import shutil, glob
backups = sorted(glob.glob(API + ".bak-conv-api-*"))
if backups:
    latest = backups[-1]
    shutil.copy2(latest, API)
    print(f"[OK] Restore depuis {os.path.basename(latest)}")

with open(API, "r", encoding="utf-8-sig") as f:
    content = f.read()
    lines = content.split("\n")

# Cherche tous les decorateurs @app.X et le dernier
print(f"\nTotal lignes : {len(lines)}")
print()

# Cherche les "if __name__"
print("--- if __name__ ---")
for i, ln in enumerate(lines, 1):
    if "if __name__" in ln:
        print(f"  L{i}: {ln}")

# Cherche le dernier @app endpoint
print("\n--- Derniers @app.X ---")
last_routes = []
for i, ln in enumerate(lines, 1):
    if ln.startswith("@app."):
        last_routes.append((i, ln))
for i, ln in last_routes[-10:]:
    print(f"  L{i}: {ln}")

# Affiche les 30 dernieres lignes du fichier
print("\n--- 40 dernieres lignes ---")
for i, ln in enumerate(lines[-40:], len(lines) - 39):
    print(f"  L{i}: {ln}")

# Cherche la 1ere occurrence du contenu apres position 883 environ
print("\n--- Lignes 870-895 ---")
for i, ln in enumerate(lines[869:895], 870):
    print(f"  L{i}: {ln}")
