"""
Diag : verifier que les patches HTML + JS UI backtest regime sont bien appliques
et structurellement bons cote fichier (vs ce que le navigateur charge peut-etre encore depuis cache).
ASCII pur.
"""
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def rd(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

print("=" * 70)
print("DIAG UI BACKTEST REGIME - PATCH APPLIQUE ?")
print("=" * 70)

# 1) index.html : marker present et a quels endroits ?
html_path = os.path.join(ROOT, "index.html")
html = rd(html_path)
print("\n[1] index.html :")
print(f"  fichier: {len(html)} chars, {len(html.splitlines())} lignes")
print(f"  marker '[PATCH_UI_BACKTEST_REGIME_V1]' (HTML): {html.count('[PATCH_UI_BACKTEST_REGIME_V1]')}")
print(f"  'id=\"btApplyRegime\"': {html.count('btApplyRegime')}")
print(f"  'id=\"btRegimePanel\"': {html.count('btRegimePanel')}")
print(f"  'id=\"btRegimeBody\"': {html.count('btRegimeBody')}")

# Localiser les lignes
for keyword in ['btApplyRegime', 'btRegimePanel', 'btRegimeBody']:
    for i, ln in enumerate(html.splitlines(), 1):
        if keyword in ln:
            print(f"  L{i} '{keyword}': {ln.strip()[:120]}")
            break

# 2) app.js : marker et helpers
js_path = os.path.join(ROOT, "app.js")
js = rd(js_path)
print("\n[2] app.js :")
print(f"  fichier: {len(js)} chars, {len(js.splitlines())} lignes")
print(f"  marker '[PATCH_UI_BACKTEST_REGIME_V1]': {js.count('[PATCH_UI_BACKTEST_REGIME_V1]')}")
print(f"  'function renderBacktestRegime': {js.count('function renderBacktestRegime')}")
print(f"  'renderBacktestRegime(data)': {js.count('renderBacktestRegime(data)')}")
print(f"  'apply_regime: applyRegime': {js.count('apply_regime: applyRegime')}")
print(f"  'const applyRegime': {js.count('const applyRegime')}")

# Localiser les declarations
for keyword in ['function renderBacktestRegime', 'const applyRegime', 'apply_regime: applyRegime']:
    for i, ln in enumerate(js.splitlines(), 1):
        if keyword in ln:
            print(f"  L{i} '{keyword[:40]}': {ln.strip()[:160]}")
            break

# 3) Verifier le contexte de l'injection dans runBacktest
print("\n[3] Bloc runBacktest body (declaration applyRegime + body POST) :")
m = re.search(r"async\s+function\s+runBacktest\s*\(", js)
if m:
    # afficher les 35 premieres lignes apres la fonction
    js_lines = js.splitlines()
    start_line = js[:m.start()].count("\n")
    for i in range(start_line, min(start_line + 35, len(js_lines))):
        ln = js_lines[i]
        if "applyRegime" in ln or "apiFetch" in ln or "JSON.stringify" in ln or "}" == ln.strip():
            print(f"  L{i+1}: {ln.rstrip()[:170]}")

# 4) Verifier le contexte renderBacktestResults : appel renderBacktestRegime present ?
print("\n[4] Fin de renderBacktestResults (appel renderBacktestRegime) :")
m2 = re.search(r"function\s+renderBacktestResults\s*\(", js)
if m2:
    js_lines = js.splitlines()
    start_line = js[:m2.start()].count("\n")
    # Bracket-match pour trouver la fin
    src_after = js[m2.end():]
    body_start = src_after.find("{")
    depth = 1
    i = body_start + 1
    while i < len(src_after):
        if src_after[i] == '{': depth += 1
        elif src_after[i] == '}':
            depth -= 1
            if depth == 0: break
        i += 1
    body_end_abs = m2.end() + i
    body_end_line = js[:body_end_abs].count("\n")
    # Afficher les 8 dernieres lignes avant la fermeture
    for k in range(max(start_line, body_end_line - 8), body_end_line + 1):
        print(f"  L{k+1}: {js_lines[k].rstrip()[:170]}")

# 5) Helper en fin de fichier ?
print("\n[5] Helper renderBacktestRegime en fin de fichier :")
m3 = re.search(r"function\s+renderBacktestRegime\s*\(", js)
if m3:
    line_n = js[:m3.start()].count("\n") + 1
    print(f"  function renderBacktestRegime trouvee L{line_n}")
    # afficher 5 lignes
    js_lines = js.splitlines()
    for i in range(line_n - 1, min(line_n + 8, len(js_lines))):
        print(f"  L{i+1}: {js_lines[i].rstrip()[:170]}")
else:
    print("  ABSENT - le helper n'a pas ete injecte !")

# 6) Check version query-string dans index.html pour app.js
print("\n[6] Query-string version sur app.js dans index.html :")
m4 = re.findall(r'app\.js\?v=([^"\']+)', html)
print(f"  versions trouvees: {m4}")

print("\nDONE")
