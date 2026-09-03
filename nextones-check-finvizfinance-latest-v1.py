"""
Diag rapide : quelle est la derniere version disponible de finvizfinance sur PyPI ?
Actuellement installee : 1.3.0 (bug HTML parsing)
"""
import subprocess
import sys

print("[STAGE 1] Version installee vs derniere PyPI")
print("-" * 70)

# Version installee
try:
    r = subprocess.run(
        ["py", "-3.13", "-m", "pip", "show", "finvizfinance"],
        capture_output=True, text=True, timeout=15
    )
    for line in r.stdout.splitlines():
        if line.startswith("Version:"):
            print(f"  INSTALLED  {line}")
except Exception as e:
    print(f"  [ERR pip show] {e}")

# Versions disponibles (pip index versions - PyPI)
try:
    r = subprocess.run(
        ["py", "-3.13", "-m", "pip", "index", "versions", "finvizfinance"],
        capture_output=True, text=True, timeout=30
    )
    print()
    print("  [pip index versions]")
    print(r.stdout[:800])
    if r.stderr:
        print("  [stderr]", r.stderr[:400])
except Exception as e:
    print(f"  [ERR pip index] {e}")

# Fallback : json PyPI
print()
print("[STAGE 2] PyPI JSON metadata")
print("-" * 70)
try:
    import urllib.request
    import json
    resp = urllib.request.urlopen("https://pypi.org/pypi/finvizfinance/json", timeout=15)
    data = json.loads(resp.read())
    latest = data.get("info", {}).get("version")
    print(f"  latest version on PyPI: {latest}")

    # Historique releases (par date)
    releases = data.get("releases", {})
    dated = []
    for ver, files in releases.items():
        if files:
            upload = files[0].get("upload_time", "")
            dated.append((upload, ver))
    dated.sort(reverse=True)
    print()
    print("  10 derniers releases :")
    for upload, ver in dated[:10]:
        print(f"    {upload[:10]}  {ver}")
except Exception as e:
    print(f"  [ERR PyPI] {type(e).__name__}: {e}")
