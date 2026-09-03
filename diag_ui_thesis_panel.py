"""Diagnostique : le patch UI Thesis Challenge V2 est-il bien dans les fichiers servis ?"""
from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# Cherche tous les index.html et app.js
candidates_html = list(ROOT.rglob("index.html"))
candidates_js   = list(ROOT.rglob("app.js"))

print("=" * 70)
print("FICHIERS HTML/JS TROUVÉS")
print("=" * 70)
for p in candidates_html:
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="replace")
        has_v1_html   = "[PPLX_PANEL_V1_HTML]" in txt
        has_v2_html   = "[PPLX_THESIS_PANEL_V2_HTML]" in txt
        has_pplx_div  = "pplx-insights" in txt or "perplexity-insights" in txt.lower()
        has_thesis_div= "thesis-challenge" in txt.lower() or "thesis_challenge" in txt
        size_kb = p.stat().st_size / 1024
        print(f"\n[HTML] {p}")
        print(f"  size={size_kb:.1f} KB")
        print(f"  marker V1 (panel base)        = {has_v1_html}")
        print(f"  marker V2 (thesis challenge)  = {has_v2_html}")
        print(f"  contient div 'pplx-insights'  = {has_pplx_div}")
        print(f"  contient 'thesis-challenge'   = {has_thesis_div}")
    except Exception as e:
        print(f"[HTML] {p} -> ERREUR {e}")

print()
print("=" * 70)
for p in candidates_js:
    try:
        txt = p.read_text(encoding="utf-8-sig", errors="replace")
        has_v1_js   = "[PPLX_PANEL_V1_JS]" in txt
        has_v2_js   = "[PPLX_THESIS_PANEL_V2_JS]" in txt
        has_load_pplx = "loadPplxInsights" in txt or "fetch('/api/pplx" in txt or 'fetch("/api/pplx' in txt
        has_thesis_fn = "renderThesisChallenges" in txt or "thesis_challenges" in txt
        size_kb = p.stat().st_size / 1024
        print(f"\n[JS] {p}")
        print(f"  size={size_kb:.1f} KB")
        print(f"  marker V1 (panel base)        = {has_v1_js}")
        print(f"  marker V2 (thesis challenge)  = {has_v2_js}")
        print(f"  appelle /api/pplx/...         = {has_load_pplx}")
        print(f"  fonction render thesis        = {has_thesis_fn}")
    except Exception as e:
        print(f"[JS] {p} -> ERREUR {e}")

print()
print("=" * 70)
print("OÙ EST SERVI LE STATIC ? (api_server_with_static.py)")
print("=" * 70)
srv = ROOT / "api_server_with_static.py"
if srv.exists():
    txt = srv.read_text(encoding="utf-8-sig", errors="replace")
    # Cherche les StaticFiles / mount
    for m in re.finditer(r'(StaticFiles|mount|directory|static_url)\s*[=(]\s*["\']?([^"\'\)]+)', txt):
        print(f"  {m.group(0)[:120]}")
    # Cherche FileResponse("index.html")
    for m in re.finditer(r'(FileResponse|HTMLResponse|TemplateResponse|read_text)\s*\(\s*["\']?([^"\')\s]+)', txt):
        s = m.group(0)
        if "html" in s.lower() or "index" in s.lower() or "ui" in s.lower():
            print(f"  {s[:120]}")
