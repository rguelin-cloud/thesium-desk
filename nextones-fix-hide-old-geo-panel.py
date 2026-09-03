# [OLD_GDELT_PANEL_HIDDEN_V1]
# Masque l'ancien panel "Risque Geopolitique" (GDELT + USGS) qui reste bloque
# en CHARGEMENT a cause des rate limits GDELT 429.
#
# Cible : <div class="geo-section" id="geoSection"> dans tab-macro
# Methode : injection CSS #geoSection { display:none } avec marker.
#
# Idempotent : si le marker existe deja, on remplace le bloc proprement.
# Reversible : il suffit de supprimer le bloc CSS marque pour reafficher.
#
# Usage : py -3.13 nextones-fix-hide-old-geo-panel.py

from pathlib import Path
import re
import shutil
import time

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")

MARK_BEGIN = "/* [OLD_GDELT_PANEL_HIDDEN_V1] BEGIN */"
MARK_END = "/* [OLD_GDELT_PANEL_HIDDEN_V1] END */"

CSS_BLOCK = f"""
<style>
{MARK_BEGIN}
/* Masquage de l'ancien panel Risque Geopolitique (GDELT + USGS).
   Le panel Perplexity 'Contexte geopolitique IA' le remplace de facto.
   Pour reafficher : supprimer ce bloc CSS entre les markers BEGIN/END. */
#geoSection {{
  display: none !important;
}}
{MARK_END}
</style>
"""


def main():
    if not HTML.exists():
        print(f"[ERR] HTML introuvable : {HTML}")
        return

    raw = HTML.read_text(encoding="utf-8-sig", errors="replace")
    print(f"[INFO] Fichier : {HTML}")
    print(f"[INFO] Taille avant : {len(raw)} chars")

    # Verifie que la cible existe
    if 'id="geoSection"' not in raw:
        print('[ERR] id="geoSection" introuvable, abort')
        return
    print('[OK]   Cible id="geoSection" trouvee')

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = HTML.with_suffix(f".html.bak.{ts}")
    shutil.copy2(HTML, backup)
    print(f"[OK]   Backup : {backup}")

    # Supprime ancien bloc CSS V1 s'il existe (idempotent)
    pattern = re.compile(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), re.DOTALL)
    if MARK_BEGIN in raw:
        raw = pattern.sub("", raw)
        # Supprime aussi le <style></style> vide qui resterait potentiellement
        raw = re.sub(r"<style>\s*</style>", "", raw)
        print("[OK]   Ancien bloc CSS V1 supprime")
    else:
        print("[OK]   Pas d'ancien bloc CSS V1 (premiere injection)")

    # Injecte avant </head> (place naturelle pour du CSS global)
    if "</head>" not in raw:
        print("[ERR]  </head> introuvable, abort")
        return
    raw_new = raw.replace("</head>", CSS_BLOCK + "</head>", 1)
    delta = len(raw_new) - len(raw)
    print(f"[INFO] Taille apres : {len(raw_new)} chars (+{delta})")

    HTML.write_text(raw_new, encoding="utf-8", newline="\n")
    print("[OK]   Ecriture index.html (utf-8 sans BOM)")

    # Validation
    check = HTML.read_text(encoding="utf-8-sig", errors="replace")
    tags = [MARK_BEGIN, MARK_END, "#geoSection", 'id="geoSection"']
    print("\n[VALIDATION]")
    all_ok = True
    for t in tags:
        n = check.count(t)
        flag = "OK" if n >= 1 else "MISS"
        if n < 1:
            all_ok = False
        print(f"  [{flag}] {t:45} count={n}")

    if all_ok:
        print("\n[SUCCESS] Patch applique. Hard refresh navigateur (Ctrl+Shift+R).")
        print("          L'ancien panel GDELT/USGS doit avoir disparu.")
        print("          Le panel Perplexity 'Contexte geopolitique IA' reste visible.")
    else:
        print("\n[FAIL] Validation incomplete.")


if __name__ == "__main__":
    main()
