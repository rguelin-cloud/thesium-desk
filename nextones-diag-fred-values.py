# Diag : pourquoi GDP=31856.3 (niveau) au lieu de pct_chg, et pourquoi Jobless=209K (valeur du 21/05) au lieu du 28/05.
# Inspecte :
#   - RELEASE_MAP (series, fmt)
#   - Le code qui appele FRED et qui construit "actual"
#   - Les valeurs brutes que FRED renvoie pour les 2 series

from pathlib import Path
import re
import os
import json
import urllib.request
import urllib.parse

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DM = ROOT / "data_macro.py"

print("=" * 80)
print("[1] RELEASE_MAP : entrees GDP + Jobless Claims")
print("=" * 80)
txt = DM.read_text(encoding="utf-8-sig", errors="replace")

# Trouver RELEASE_MAP
m = re.search(r"RELEASE_MAP\s*=\s*\{(.*?)^\}", txt, re.S | re.M)
if m:
    block = m.group(1)
    # GDP
    for key in ["GDP", "Initial Jobless", "Jobless", "53", "175"]:
        for line in block.splitlines():
            if key in line:
                print(f"  {line.strip()[:180]}")

print()
print("=" * 80)
print("[2] Branches de dispatch (pct_chg / claims_k) - extrait")
print("=" * 80)
# Cherche les blocs if fmt == ...
for fmt_name in ["pct_chg", "claims_k"]:
    pat = re.compile(rf'fmt\s*==\s*[\'"]{fmt_name}[\'"]', re.S)
    for m in pat.finditer(txt):
        start = max(0, m.start() - 50)
        end = min(len(txt), m.end() + 600)
        print(f"\n  -- fmt == {fmt_name} (pos {m.start()}) --")
        snippet = txt[start:end]
        for line in snippet.splitlines()[:20]:
            print(f"    {line}")

print()
print("=" * 80)
print("[3] Cherche le code qui appelle FRED API (urlopen / requests / fred)")
print("=" * 80)
for pat in [r"fred[a-z_]*\(", r"observations", r"series_id", r"api\.stlouisfed"]:
    for m in re.finditer(pat, txt, re.I):
        ln = txt[:m.start()].count("\n") + 1
        line = txt.splitlines()[ln - 1] if ln <= len(txt.splitlines()) else ""
        print(f"  L{ln:>4} : {line.strip()[:160]}")

print()
print("=" * 80)
print("[4] Test direct FRED API : GDP serie + ICSA (Initial Claims)")
print("=" * 80)
# Cherche cle FRED dans .env ou variables
api_key = os.environ.get("FRED_API_KEY", "")
if not api_key:
    # Cherche dans .env
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "FRED" in line.upper() and "=" in line:
                api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                print(f"  [INFO] FRED key trouvee dans .env (longueur={len(api_key)})")
                break

if not api_key:
    print("  [WARN] FRED_API_KEY introuvable, test API skip")
else:
    for series_id, label in [("GDP", "GDP niveau"),
                             ("A191RL1Q225SBEA", "Real GDP pct chg SAAR"),
                             ("GDPC1", "Real GDP chained"),
                             ("ICSA", "Initial Claims SA")]:
        try:
            url = ("https://api.stlouisfed.org/fred/series/observations"
                   f"?series_id={series_id}&api_key={api_key}&file_type=json"
                   "&sort_order=desc&limit=4")
            req = urllib.request.Request(url, headers={"User-Agent": "diag-fred/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            obs = data.get("observations", [])[:4]
            print(f"\n  [{series_id}] {label} - 4 dernieres obs :")
            for o in obs:
                print(f"    {o.get('date')} = {o.get('value')}")
        except Exception as e:
            print(f"  [ERR] {series_id} : {e}")

print()
print("=" * 80)
print("[5] Verifie si le code prend la 'derniere observation' ou filtre sur date")
print("=" * 80)
# Cherche limit=1, sort_order, observation_start
for pat in [r"limit\s*=\s*\d+", r"observation_start", r"observation_end",
            r"sort_order", r"\[-1\]", r"observations\[0\]"]:
    for m in re.finditer(pat, txt):
        ln = txt[:m.start()].count("\n") + 1
        line = txt.splitlines()[ln - 1] if ln <= len(txt.splitlines()) else ""
        print(f"  L{ln:>4} : {line.strip()[:160]}")

print()
print("[DONE]")
