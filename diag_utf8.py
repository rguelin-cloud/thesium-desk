# =====================================================================
# diag_utf8.py
# Trouve la cause exacte du mojibake UI (e.g. "Ã©" au lieu de "é")
# =====================================================================
from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

print("=" * 70)
print("  DIAGNOSTIC MOJIBACHE UI")
print("=" * 70)

# ---------------------------------------------------------------------
# 1. api_server_with_static.py - voir comment les statics sont servis
# ---------------------------------------------------------------------
print()
print("[1] api_server_with_static.py - service des fichiers statiques")
print("-" * 70)
api_path = ROOT / "api_server_with_static.py"
src = api_path.read_text(encoding="utf-8", errors="ignore")

# Cherche StaticFiles, FileResponse, mount, charset, media_type
patterns = [
    r"StaticFiles\([^)]*\)",
    r"FileResponse\([^)]*\)",
    r"app\.mount\([^)]*\)",
    r"media_type\s*=\s*['\"][^'\"]+['\"]",
    r"charset",
    r"text/html",
]
for p in patterns:
    for m in re.finditer(p, src):
        ln = src[:m.start()].count("\n") + 1
        line = src.splitlines()[ln-1].strip()[:90]
        print(f"  L{ln:<4} {line}")

# ---------------------------------------------------------------------
# 2. Lister les fichiers HTML / JS / CSS dans static/
# ---------------------------------------------------------------------
print()
print("[2] Fichiers HTML / JS dans static/ (encodage detecte)")
print("-" * 70)

static_candidates = [ROOT / "static", ROOT / "frontend", ROOT / "public",
                     ROOT / "ui", ROOT / "templates", ROOT / "www"]

for stat in static_candidates:
    if not stat.exists():
        continue
    print(f"  Dossier : {stat}")
    for ext in ["*.html", "*.js", "*.css"]:
        for f in stat.rglob(ext):
            # Lit les premiers octets pour detecter BOM / encodage
            raw = f.read_bytes()[:300]
            has_bom = raw.startswith(b"\xef\xbb\xbf")

            # Cherche meta charset dans HTML
            charset = "?"
            if f.suffix == ".html":
                try:
                    txt = raw.decode("utf-8", errors="ignore")
                    m = re.search(r'<meta[^>]*charset\s*=\s*["\']?([^"\'>\s]+)', txt, re.IGNORECASE)
                    if m: charset = m.group(1)
                except Exception:
                    charset = "decode_error"

            # Cherche le bug typique : "Ã©" (utf-8 décodé en latin-1)
            has_mojibake_src = b"\xc3\xa9" in raw  # vrai "é" en UTF-8 (normal, OK)

            rel = f.relative_to(ROOT)
            tags = []
            if has_bom: tags.append("BOM")
            if charset != "?": tags.append(f"meta:{charset}")
            tag_str = "  ".join(tags) if tags else "-"
            print(f"    {str(rel):<60}  {tag_str}")

# ---------------------------------------------------------------------
# 3. Test : verifier qu'un HTML contient bien des accents non casses
# ---------------------------------------------------------------------
print()
print("[3] Recherche fichier contenant 'IDEAL' / 'basees' / 'Modifier'")
print("-" * 70)
for stat in static_candidates:
    if not stat.exists():
        continue
    for f in stat.rglob("*.html"):
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "IDÉAL" in txt or "IDEAL" in txt or "basées" in txt or "PORTFOLIO" in txt.upper():
            print(f"  Trouve dans : {f.relative_to(ROOT)}")
            # Affiche les lignes pertinentes
            for ln, line in enumerate(txt.splitlines(), 1):
                if any(kw in line for kw in ["IDÉAL", "basées", "—", "30 DAYS", "Modifier"]):
                    print(f"    L{ln}: {line.strip()[:120]}")

print()
print("=" * 70)
print("  Diagnostic mojibake termine")
print("=" * 70)
print()
print("  CAUSE LA PLUS PROBABLE :")
print("  - HTML servi sans 'charset=utf-8' dans Content-Type")
print("  - Solution : ajouter <meta charset='UTF-8'> dans <head> OU")
print("    forcer media_type='text/html; charset=utf-8' cote FastAPI")
