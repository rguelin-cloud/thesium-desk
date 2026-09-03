# [DIAG_GEO_UI_EXTRACT_JS_V1]
# Extrait toutes les fonctions JS liees au panel geo presentes dans index.html
# pour comprendre quelle version y vit reellement.

from pathlib import Path
import re

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
raw = HTML.read_text(encoding="utf-8-sig", errors="replace")

print(f"Fichier   : {HTML}")
print(f"Taille    : {len(raw)} chars")
print()

# Cherche tous les markers PPLX_GEO*
print("=" * 72)
print("MARKERS PPLX_GEO* presents dans le fichier")
print("=" * 72)
for m in re.finditer(r"\[?PPLX_GEO[A-Z0-9_]+\]?", raw):
    print(f"  pos={m.start():>6}  {m.group(0)}")

print()
print("=" * 72)
print("Toutes les fonctions JS contenant 'pplxGeo' ou 'PplxGeo'")
print("=" * 72)
# cherche les definitions de fonctions
for m in re.finditer(r"(function\s+(\w*[Pp]plx[Gg]eo\w*)|window\.(\w*[Pp]plx[Gg]eo\w*)\s*=)", raw):
    name = m.group(2) or m.group(3)
    pos = m.start()
    snippet = raw[pos:pos + 200].replace("\n", " ")
    print(f"\n  pos={pos}  name={name}")
    print(f"  {snippet}")

print()
print("=" * 72)
print("Recherche : pplxRenderRisks / pplxRenderExposure / pplxRisksGrid")
print("=" * 72)
for tok in ["pplxRenderRisks", "pplxRenderExposure", "pplxRisksGrid", "pplxGeoRisksGrid", "pplxGeoExposureList"]:
    n = raw.count(tok)
    print(f"  {tok:25} count={n}")

print()
print("=" * 72)
print("HTML autour de pplxGeoExposureList (pour voir si une grille soeur existe)")
print("=" * 72)
m = re.search(r'id="pplxGeoExposureList"', raw)
if m:
    pos = m.start()
    print(raw[max(0, pos - 600):pos + 600])

print()
print("=" * 72)
print("Bloc complet loadPplxGeoData")
print("=" * 72)
m = re.search(r"loadPplxGeoData\s*=\s*async\s+function", raw)
if m:
    pos = m.start()
    # cherche fin probable
    end = raw.find("};", pos)
    if end > 0:
        print(raw[pos:end + 2])
    else:
        print(raw[pos:pos + 1500])
