# [DIAG_GEO_UI_CHARGE_V1]
# Diagnostic cote UI : pourquoi le panel geo affiche CHARGEMENT alors
# que /api/pplx/geo renvoie available=True.
#
# Verifie :
#   1) Les IDs DOM attendus par loadPplxGeoData sont presents dans index.html
#   2) Le bloc JS [PPLX_GEO_PANEL_V1] est present
#   3) Le marker section [PPLX_GEO_SECTION_V1] existe
#   4) Aucun autre script ne court-circuite loadPplxGeoData
#   5) Le tab macro contient bien la section
#
# Usage : py -3.13 nextones-diag-geo-ui-charge-pas.py

from pathlib import Path
import re

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\static\index.html")


def section(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


def main():
    if not HTML.exists():
        # Essai alternatif
        alt = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
        if alt.exists():
            target = alt
        else:
            print(f"  HTML INTROUVABLE : {HTML}")
            return
    else:
        target = HTML

    raw = target.read_text(encoding="utf-8-sig", errors="replace")
    print(f"  Fichier : {target}")
    print(f"  Taille  : {len(raw)} chars")

    section("[1/5] IDs DOM attendus par loadPplxGeoData")
    ids = [
        "pplxGeoSection",
        "pplxGeoScoreValue",
        "pplxGeoRegimeBadge",
        "pplxGeoSummary",
        "pplxGeoTimestamp",
        "pplxGeoRisksGrid",
        "pplxGeoExposureList",
    ]
    for i in ids:
        n = raw.count(f'id="{i}"')
        flag = "OK " if n == 1 else ("MULTI" if n > 1 else "MISS")
        print(f"  [{flag}] id={i:25} occurrences={n}")

    section("[2/5] Bloc JS [PPLX_GEO_PANEL_V1]")
    markers_js = [
        "PPLX_GEO_PANEL_V1_JS_BEGIN",
        "PPLX_GEO_PANEL_V1_JS_END",
        "loadPplxGeoData",
        "pplxRenderRisks",
        "pplxRenderExposure",
        "pplxBoot",
    ]
    for m in markers_js:
        n = raw.count(m)
        flag = "OK" if n >= 1 else "MISS"
        print(f"  [{flag}] {m:35} count={n}")

    section("[3/5] Bloc HTML section [PPLX_GEO_SECTION_V1]")
    markers_html = [
        "PPLX_GEO_SECTION_V1_BEGIN",
        "PPLX_GEO_SECTION_V1_END",
        "pplx-geo-section",
    ]
    for m in markers_html:
        n = raw.count(m)
        flag = "OK" if n >= 1 else "MISS"
        print(f"  [{flag}] {m:35} count={n}")

    section("[4/5] CSS class .pplx-loading / skeleton")
    n_loading = len(re.findall(r"pplx-loading", raw))
    n_skel = len(re.findall(r"skeleton", raw, re.IGNORECASE))
    n_charge = len(re.findall(r"CHARGEMENT", raw, re.IGNORECASE))
    print(f"  .pplx-loading  count = {n_loading}")
    print(f"  skeleton       count = {n_skel}")
    print(f"  CHARGEMENT     count = {n_charge}")

    section("[5/5] Position section dans le DOM (tab macro ?)")
    m = re.search(r'id="pplxGeoSection"', raw)
    if m:
        pos = m.start()
        # remonte 2000 chars pour voir le contexte parent
        before = raw[max(0, pos - 2500):pos]
        # cherche le data-tab le plus proche en amont
        tabs = list(re.finditer(r'(data-tab="[^"]+"|id="tab-[^"]+")', before))
        if tabs:
            last_tab = tabs[-1].group(0)
            print(f"  pplxGeoSection est apres : {last_tab}")
        else:
            print("  pplxGeoSection : aucun tab parent detecte dans 2500 chars precedents")
        # apercu du HTML autour de l'ID
        snippet = raw[max(0, pos - 200):pos + 500].replace("\n", " ")
        print("\n  Apercu :")
        print(f"  ...{snippet[:600]}...")
    else:
        print("  pplxGeoSection ABSENT du DOM -> le panel n'est meme pas dans la page")

    section("[FIN]")
    print("  Si tous les IDs sont OK et JS present, ouvre la console navigateur (F12),")
    print("  va sur l'onglet macro, et copie-colle les erreurs JS rouges qui apparaissent.")
    print("  Lance aussi : window.loadPplxGeoData(true) dans la console pour voir le retour.")


if __name__ == "__main__":
    main()
