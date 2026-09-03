# nextones-find-bearer-token.py
# Cherche ou est defini le BEARER token et comment l'auth est verifiee
# Inspecte api_server.py + .env + variables env

from pathlib import Path
import os, re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

print("=" * 70)
print("[1] Recherche de tokens dans .env / config files")
print("=" * 70)
for name in [".env", ".env.local", "config.json", "config.py", "settings.py"]:
    p = ROOT / name
    if p.exists():
        print(f"\n--- {p} ---")
        try:
            content = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            content = p.read_text(encoding="latin-1", errors="replace")
        for line in content.splitlines():
            if re.search(r"(token|bearer|api[_-]?key|secret|auth)", line, re.IGNORECASE):
                # masque valeur apres =
                if "=" in line:
                    k, v = line.split("=", 1)
                    masked = v[:8] + "..." + v[-4:] if len(v) > 12 else v
                    print(f"  {k}= {masked}")
                else:
                    print(f"  {line[:80]}")

print("\n" + "=" * 70)
print("[2] Recherche dans api_server.py / api_server_with_static.py")
print("=" * 70)
for fname in ["api_server.py", "api_server_with_static.py"]:
    p = ROOT / fname
    if not p.exists():
        continue
    print(f"\n--- {fname} ---")
    try:
        content = p.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        content = p.read_text(encoding="latin-1", errors="replace")
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if re.search(r"(bearer|HTTPBearer|verify_token|get_current_user|Depends.*auth|401|api[_-]?key|BEARER_TOKEN|AUTH_TOKEN)", line, re.IGNORECASE):
            print(f"  L{i}: {line.rstrip()[:120]}")

print("\n" + "=" * 70)
print("[3] Variables d'environnement actuelles")
print("=" * 70)
for k, v in os.environ.items():
    if re.search(r"(token|bearer|auth|api[_-]?key|secret)", k, re.IGNORECASE):
        masked = v[:8] + "..." + v[-4:] if len(v) > 12 else "(short)"
        print(f"  {k} = {masked}")

print("\n" + "=" * 70)
print("[4] Test endpoint public (sans auth)")
print("=" * 70)
import urllib.request
for url in ["http://127.0.0.1:8000/api/health", "http://127.0.0.1:8000/api/state", "http://127.0.0.1:8000/"]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            print(f"  {url} -> {r.status}")
    except Exception as e:
        print(f"  {url} -> {e}")
