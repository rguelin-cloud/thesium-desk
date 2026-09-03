# Trouve la cle FRED + interroge FRED direct pour GDP / GDPC1 / A191RL1Q225SBEA / ICSA
# Puis affiche RELEASE_MAP entries pour rid=53 (GDP) et rid=175 (Jobless)

from pathlib import Path
import re
import os
import json
import urllib.request

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DM = ROOT / "data_macro.py"

print("=" * 80)
print("[1] Chercher cle FRED dans tous les .env / config")
print("=" * 80)
api_key = None
candidates = [
    ROOT / ".env",
    ROOT / ".env.local",
    ROOT / "config.py",
    ROOT / "settings.py",
    ROOT / "secrets.py",
]
for c in candidates:
    if c.exists():
        txt = c.read_text(encoding="utf-8-sig", errors="replace")
        for line in txt.splitlines():
            if "FRED" in line.upper() and ("=" in line or ":" in line):
                print(f"  [{c.name}] {line.strip()[:120]}")
                # extract
                m = re.search(r'["\']?([A-Za-z0-9]{30,})["\']?', line)
                if m and not api_key:
                    api_key = m.group(1)

# Cherche aussi dans data_macro.py (constante FRED_API_KEY)
txt = DM.read_text(encoding="utf-8-sig", errors="replace")
m = re.search(r"FRED_API_KEY\s*=\s*['\"]([A-Za-z0-9]+)['\"]", txt)
if m:
    print(f"  [data_macro.py] FRED_API_KEY = {m.group(1)[:8]}...")
    if not api_key:
        api_key = m.group(1)
m = re.search(r"FRED_API_KEY\s*=\s*os\.environ\.get\(['\"]([^'\"]+)['\"]", txt)
if m:
    print(f"  [data_macro.py] FRED_API_KEY = os.environ.get('{m.group(1)}')")

if not api_key:
    # Variable env directe
    api_key = os.environ.get("FRED_API_KEY", "")
    if api_key:
        print(f"  [ENV] FRED_API_KEY trouvee : {api_key[:8]}...")

if not api_key:
    print("\n[ERR] Aucune cle FRED trouvee. Tape la cle manuellement dans une variable :")
    print("      $env:FRED_API_KEY='xxxx' ; py -3.13 .\\nextones-diag-fred-key-and-values.py")
else:
    print(f"\n  [OK] cle FRED utilisee : {api_key[:8]}...")

print()
print("=" * 80)
print("[2] RELEASE_MAP entries pour GDP (rid=53) et Jobless (rid=175)")
print("=" * 80)
m = re.search(r"RELEASE_MAP\s*=\s*\{(.*?)^\}", txt, re.S | re.M)
if m:
    block = m.group(1)
    # Affiche lignes contenant 53: ou 175:
    for line in block.splitlines():
        s = line.strip()
        if s.startswith("53:") or s.startswith("175:") or "rid=53" in s or "rid=175" in s:
            print(f"  {s[:200]}")
    # Sinon affiche toutes les lignes avec GDP ou Jobless
    print("\n  -- toutes les lignes contenant GDP / Jobless / Claims --")
    for line in block.splitlines():
        if any(k in line for k in ["GDP", "Jobless", "Claims", "ICSA", "Initial"]):
            print(f"  {line.strip()[:200]}")
else:
    print("  [ERR] RELEASE_MAP non trouve")

print()
print("=" * 80)
print("[3] Test FRED direct : GDP / GDPC1 / A191RL1Q225SBEA / ICSA")
print("=" * 80)
if api_key:
    for sid, label in [
        ("GDP", "GDP niveau (milliards $)"),
        ("GDPC1", "Real GDP chained (milliards)"),
        ("A191RL1Q225SBEA", "Real GDP % chg SAAR"),
        ("ICSA", "Initial Claims SA"),
    ]:
        try:
            url = ("https://api.stlouisfed.org/fred/series/observations"
                   f"?series_id={sid}&api_key={api_key}&file_type=json"
                   "&sort_order=desc&limit=4")
            req = urllib.request.Request(url, headers={"User-Agent": "diag/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            obs = data.get("observations", [])[:4]
            print(f"\n  [{sid}] {label}")
            for o in obs:
                print(f"    {o.get('date')} = {o.get('value')}")
        except Exception as e:
            print(f"  [ERR] {sid} : {e}")

print()
print("[DONE]")
