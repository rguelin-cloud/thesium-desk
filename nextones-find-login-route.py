# nextones-find-login-route.py
# Identifie la route login + champs requis + liste les users en base

from pathlib import Path
import re, sqlite3

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"

print("=" * 70)
print("[1] Routes auth dans api_server.py (autour L1795-1815)")
print("=" * 70)
p = ROOT / "api_server.py"
content = p.read_text(encoding="utf-8-sig", errors="replace")
lines = content.splitlines()

# affiche +/- 30 lignes autour des routes auth
for target in [1780, 1795, 1805]:
    print(f"\n--- Bloc autour L{target} ---")
    for i in range(max(0, target-15), min(len(lines), target+20)):
        print(f"  L{i+1}: {lines[i].rstrip()[:140]}")

print("\n" + "=" * 70)
print("[2] Recherche routes /api/auth/* et /login")
print("=" * 70)
for i, line in enumerate(lines, 1):
    if re.search(r"@app\.(post|get).*?(login|register|auth|token)", line, re.IGNORECASE):
        print(f"  L{i}: {line.rstrip()[:140]}")
        # affiche les 8 lignes suivantes (signature + debut fonction)
        for j in range(i, min(i+8, len(lines))):
            print(f"  L{j+1}: {lines[j].rstrip()[:140]}")
        print()

print("\n" + "=" * 70)
print("[3] Users en base")
print("=" * 70)
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%'")
for (t,) in cur.fetchall():
    print(f"\n--- table {t} ---")
    cur.execute(f"PRAGMA table_info({t})")
    cols = [c[1] for c in cur.fetchall()]
    print(f"  cols: {cols}")
    cur.execute(f"SELECT * FROM {t} LIMIT 10")
    for row in cur.fetchall():
        # masque mot de passe hash
        masked = []
        for col, val in zip(cols, row):
            if col.lower() in ("password", "password_hash", "hashed_password", "hash"):
                masked.append(f"{col}=***")
            else:
                masked.append(f"{col}={val}")
        print(f"  {', '.join(masked)}")
conn.close()
