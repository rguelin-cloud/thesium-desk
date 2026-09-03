# Compare les series FRED pour identifier celle qui donne le "Advance Estimate" original (1.6% Q1 2026).
# - A191RL1Q225SBEA : Real GDP % chg SAAR (revise a chaque release)
# - GDPA            : GDP Advance Estimate ? (a verifier)
# - A191RL1Q020SBEA : Real GDP YoY ?
# + ALFRED : vintage de la 1re publication (Advance)

from pathlib import Path
import re
import urllib.request
import json

DM = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
txt = DM.read_text(encoding="utf-8-sig", errors="replace")
m = re.search(r"FRED_API_KEY\s*=\s*['\"]([A-Za-z0-9]+)['\"]", txt)
KEY = m.group(1) if m else ""
print(f"Key : {KEY[:8]}...")

# Series candidats
series_list = [
    ("A191RL1Q225SBEA", "Real GDP % chg SAAR (current release)"),
    ("A191RP1Q027SBEA", "Nominal GDP % chg SAAR"),
    ("GDPC1",           "Real GDP chained (level)"),
    ("GDP",             "Nominal GDP (level)"),
]

print("\n=== [1] Latest observations sur chaque serie ===")
for sid, lbl in series_list:
    try:
        url = (f"https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={sid}&api_key={KEY}&file_type=json"
               f"&sort_order=desc&limit=4")
        req = urllib.request.Request(url, headers={"User-Agent": "diag/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        obs = data.get("observations", [])[:4]
        print(f"\n  [{sid}] {lbl}")
        for o in obs:
            print(f"    {o.get('date')} = {o.get('value')}")
    except Exception as e:
        print(f"  [ERR] {sid} : {e}")

print("\n=== [2] ALFRED vintage : Premiere publication (Advance) pour Q1 2026 ===")
# ALFRED retourne la valeur telle qu'elle etait a une date de vintage donnee
# Pour Q1 2026, l'Advance Estimate sort fin avril 2026
# On demande la valeur de A191RL1Q225SBEA pour observation_date=2026-01-01 telle qu'elle etait
# disponible le 2026-04-30 (1ere publication)
for sid in ["A191RL1Q225SBEA"]:
    try:
        url = (f"https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={sid}&api_key={KEY}&file_type=json"
               f"&observation_start=2026-01-01&observation_end=2026-01-01"
               f"&realtime_start=2026-04-25&realtime_end=2026-05-15"
               f"&output_type=2")
        # output_type=2 : ALFRED toutes les vintages dans la fenetre
        req = urllib.request.Request(url, headers={"User-Agent": "diag/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        print(f"\n  [{sid}] vintages Q1 2026 entre 25/04 et 15/05 :")
        print(json.dumps(data, indent=2)[:2000])
    except Exception as e:
        print(f"  [ERR] {sid} ALFRED : {e}")

print("\n=== [3] Liste des releases FRED pour rid=53 (BEA GDP) ===")
# Pour voir les dates de release reelles
try:
    url = (f"https://api.stlouisfed.org/fred/release/dates"
           f"?release_id=53&api_key={KEY}&file_type=json"
           f"&sort_order=desc&limit=10")
    req = urllib.request.Request(url, headers={"User-Agent": "diag/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    print(f"  10 dernieres dates de release rid=53 :")
    for d in data.get("release_dates", []):
        print(f"    {d.get('date')}")
except Exception as e:
    print(f"  [ERR] release/dates : {e}")

print("\n[DONE]")
