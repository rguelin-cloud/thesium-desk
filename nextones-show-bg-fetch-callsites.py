# [SHOW_BG_FETCH_CALLSITES_V1]
# Trouve tous les call-sites de start_background_fetch et fetch_geopolitical_risk
# dans tout le projet ThesiumDesk.
#
# Affiche aussi le corps de start_background_fetch (pour comprendre le thread)
# et les premiers refs au module data_geopolitical dans api_server.py.

from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def iter_py():
    for p in ROOT.rglob("*.py"):
        if any(part in {"__pycache__", ".venv", "venv"} for part in p.parts):
            continue
        if "_backups_" in str(p):
            continue
        if ".bak." in p.name:
            continue
        yield p

print("=" * 72)
print("[1] Call-sites de start_background_fetch / fetch_geopolitical_risk")
print("=" * 72)
for func in ["start_background_fetch", "fetch_geopolitical_risk"]:
    print(f"\n  ===== {func}() =====")
    for py in iter_py():
        try:
            t = py.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception:
            continue
        for m in re.finditer(r"\b" + re.escape(func) + r"\s*\(", t):
            line_no = t[:m.start()].count("\n") + 1
            line_start = t.rfind("\n", 0, m.start()) + 1
            line_end = t.find("\n", m.end())
            line = t[line_start:line_end].strip() if line_end > 0 else "(eof)"
            print(f"    {py.relative_to(ROOT)}:{line_no}   {line[:140]}")

print()
print("=" * 72)
print("[2] Tous les 'import data_geopolitical' et 'data_geopolitical.'")
print("=" * 72)
for py in iter_py():
    try:
        t = py.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue
    for m in re.finditer(r"\bdata_geopolitical\b", t):
        line_no = t[:m.start()].count("\n") + 1
        line_start = t.rfind("\n", 0, m.start()) + 1
        line_end = t.find("\n", m.end())
        line = t[line_start:line_end].strip() if line_end > 0 else "(eof)"
        print(f"  {py.relative_to(ROOT)}:{line_no}   {line[:140]}")

print()
print("=" * 72)
print("[3] Corps de start_background_fetch() dans data_geopolitical.py")
print("=" * 72)
geo = ROOT / "data_geopolitical.py"
if geo.exists():
    txt = geo.read_text(encoding="utf-8-sig", errors="ignore")
    m = re.search(r"^def\s+start_background_fetch\s*\(", txt, re.M)
    if m:
        body_start = m.start()
        # cherche la fin = prochaine def en debut de ligne
        next_def = re.search(r"\n(?:def|class)\s+\w", txt[m.end():])
        body_end = m.end() + (next_def.start() if next_def else 2000)
        print(txt[body_start:body_end])

print()
print("=" * 72)
print("[4] Endpoints @app.get qui appellent data_geopolitical")
print("=" * 72)
api = ROOT / "api_server.py"
if api.exists():
    txt = api.read_text(encoding="utf-8-sig", errors="ignore")
    # decoupe par @app.
    blocks = re.split(r"(?=@app\.(?:get|post|put|delete))", txt)
    for blk in blocks:
        if "data_geopolitical" in blk or "fetch_geopolitical" in blk:
            # cherche route
            m = re.search(r'@app\.(?:get|post|put|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]', blk)
            if m:
                # cherche le def
                d = re.search(r"def\s+(\w+)\s*\(", blk)
                fn = d.group(1) if d else "?"
                # snippet
                idx = blk.find("data_geopolitical")
                ctx_start = max(0, idx - 50)
                ctx_end = min(len(blk), idx + 150)
                print(f"  {m.group(1):35} -> {fn}()")
                print(f"    ... {blk[ctx_start:ctx_end].strip()[:200]} ...")
                print()
