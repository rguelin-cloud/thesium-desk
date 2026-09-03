# -*- coding: utf-8 -*-
"""
[DIAG_UI_UNIVERSE_CARD_V1]
Verifie ou la carte Universe a ete inseree dans index.html
et si l'UI servie par uvicorn est bien celle qu'on a patchee.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-diag-ui-universe-card.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = ROOT / "index.html"


def section(t):
    print("\n" + "="*70)
    print(f"  {t}")
    print("="*70)


def main():
    if not HTML.exists():
        print(f"[FAIL] {HTML} introuvable.")
        return 1

    txt = HTML.read_text(encoding="utf-8", errors="replace")
    print(f"[INFO] index.html : {len(txt)} chars, {txt.count(chr(10))} lignes")

    section("1) Markers UI Universe")
    for m in ["[UI_UNIVERSE_V1_BEGIN]", "[UI_UNIVERSE_V1_END]",
              "[UI_UNIVERSE_V2_BEGIN]", "[UI_UNIVERSE_V2_END]"]:
        n = txt.count(m)
        line = txt[:txt.index(m)].count("\n")+1 if m in txt else "-"
        print(f"  {m:30s}  count={n}  line={line}")

    section("2) Position des markers v2")
    if "[UI_UNIVERSE_V2_BEGIN]" in txt:
        pos = txt.index("[UI_UNIVERSE_V2_BEGIN]")
        # 200 chars avant et apres pour le contexte
        ctx_before = txt[max(0,pos-300):pos].splitlines()[-5:]
        ctx_after = txt[pos:pos+500].splitlines()[:8]
        print("  --- 5 lignes AVANT le marker BEGIN ---")
        for l in ctx_before:
            print(f"    {l[:120]}")
        print("  --- 8 lignes APRES le marker BEGIN ---")
        for l in ctx_after:
            print(f"    {l[:120]}")

    section("3) Structure SPA detectee ?")
    # Cherche des indices SPA Vue/React/Alpine etc.
    indicators = {
        "Vue.js (v-if)": r"\bv-if\s*=",
        "Vue.js (mounted)": r"new Vue\(",
        "React": r"ReactDOM\.render|createRoot",
        "Alpine.js": r"\bx-data\s*=|\bx-show\s*=",
        "main #app div": r'<div\s+id\s*=\s*["\']app["\']',
        "main #root div": r'<div\s+id\s*=\s*["\']root["\']',
        "router-view": r"<router-view",
        "data-view (custom SPA)": r"\bdata-view\s*=",
        "view containers": r'class=["\'][^"\']*\bview\b[^"\']*["\']',
        "page containers": r'<section[^>]*data-page',
        "showView function": r"function\s+showView|showView\s*=\s*function",
    }
    found = []
    for name, pat in indicators.items():
        n = len(re.findall(pat, txt, re.IGNORECASE))
        if n > 0:
            found.append((name, n))
            print(f"  [{n:3d}]  {name}")
    if not found:
        print("  Aucun indicateur SPA evident -> page statique probable.")

    section("4) Vues / sections principales (Today, Theses, etc.)")
    # Cherche les ids ou classes qui correspondent aux items du menu
    for kw in ["Today", "Theses", "Orders", "Market Intel", "Macro", "IC Memos",
              "Backtest", "Admin"]:
        # matche id, data-view, ou texte de menu
        matches = re.findall(rf'(id="[^"]*{kw}[^"]*"|data-view="[^"]*{kw.lower()}[^"]*")',
                             txt, re.IGNORECASE)
        if matches:
            print(f"  {kw:15s}  -> {matches[:3]}")

    section("5) </body> presence")
    body_count = txt.count("</body>")
    print(f"  </body> count: {body_count}")
    if body_count >= 1:
        # Position du dernier </body>
        last_pos = txt.rfind("</body>")
        # voir si markers V2 sont AVANT </body>
        if "[UI_UNIVERSE_V2_BEGIN]" in txt:
            v2_pos = txt.index("[UI_UNIVERSE_V2_BEGIN]")
            print(f"  marker V2 line  : {txt[:v2_pos].count(chr(10))+1}")
            print(f"  </body> line    : {txt[:last_pos].count(chr(10))+1}")
            if v2_pos < last_pos:
                print("  [OK] V2 est AVANT </body>")
            else:
                print("  [WARN] V2 est APRES </body> (probleme!)")

    section("6) Static dir servi par uvicorn ?")
    # Inspect api_server_with_static.py pour voir d'ou vient le HTML
    api = ROOT / "api_server_with_static.py"
    if api.exists():
        atxt = api.read_text(encoding="utf-8", errors="replace")
        # cherche StaticFiles + RedirectResponse + FileResponse
        for pat, label in [
            (r'StaticFiles\([^)]+\)', "StaticFiles mount"),
            (r'FileResponse\([^)]+\)', "FileResponse"),
            (r'directory\s*=\s*["\']([^"\']+)["\']', "directory="),
            (r'@app\.get\(\s*["\']/?["\']', "root route @"),
        ]:
            for m in re.finditer(pat, atxt):
                print(f"  {label:20s}  {m.group(0)[:120]}")

    print()
    print("=> Si la carte est avant </body> mais l'UI ne l'affiche pas:")
    print("   1) Force-refresh (Ctrl+Shift+R)")
    print("   2) Si SPA, il faut injecter dans le bon container de vue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
