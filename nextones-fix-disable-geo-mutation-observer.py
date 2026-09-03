# -*- coding: utf-8 -*-
"""
Fix: desactiver le MutationObserver _injectDetailButtons (texte brut)
pour ne garder QUE le bouton stylise [PPLX_GEO_BTN_PER_CARD_V1].

Strategie:
1. Backup app.js horodate
2. Dans le bloc [PPLX_GEO_DETAIL_V1], remplacer _injectDetailButtons par un no-op
3. Verifier que openGeoRiskDetail existe (alias vers pplxGeoDetailOpen si besoin)
4. Marqueur idempotent: [PPLX_GEO_INJECT_DISABLED_V1]
"""

import re
import shutil
import sys
from pathlib import Path
from datetime import datetime

APP_JS = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js")
MARKER = "[PPLX_GEO_INJECT_DISABLED_V1]"

def log(m): print(f"[fix-geo-disable] {m}")

def main():
    if not APP_JS.exists():
        log(f"ERREUR introuvable: {APP_JS}")
        sys.exit(1)

    src = APP_JS.read_text(encoding="utf-8-sig")

    if MARKER in src:
        log(f"DEJA APPLIQUE ({MARKER}). Abort.")
        sys.exit(0)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = APP_JS.with_suffix(f".js.bak-geodisable-{ts}")
    shutil.copy2(APP_JS, bak)
    log(f"Backup: {bak.name}")

    # ---------------------------------------------------------------
    # 1. Court-circuiter _injectDetailButtons en early-return
    # ---------------------------------------------------------------
    # Pattern recherche : function _injectDetailButtons() {
    # On insere "return; // [PPLX_GEO_INJECT_DISABLED_V1]" juste apres l'ouverture
    pat_func = re.compile(r"function\s+_injectDetailButtons\s*\(\s*\)\s*\{")
    m = pat_func.search(src)
    if not m:
        log("ERREUR: function _injectDetailButtons introuvable")
        sys.exit(2)

    insert_pos = m.end()
    log(f"_injectDetailButtons trouve a position {m.start()}")
    log(f"Insertion early-return apres position {insert_pos}")

    early_return = f"\n    return; // {MARKER} doublon supprime, bouton injecte directement dans pplxRenderRisks\n"
    new_src = src[:insert_pos] + early_return + src[insert_pos:]

    # ---------------------------------------------------------------
    # 2. Verifier que openGeoRiskDetail existe (alias vers pplxGeoDetailOpen)
    # ---------------------------------------------------------------
    has_open_geo = "function openGeoRiskDetail" in new_src or "window.openGeoRiskDetail" in new_src
    has_pplx_geo = "pplxGeoDetailOpen" in new_src or "window.pplxGeoDetailOpen" in new_src

    log(f"openGeoRiskDetail defini: {has_open_geo}")
    log(f"pplxGeoDetailOpen defini: {has_pplx_geo}")

    if not has_open_geo and has_pplx_geo:
        # Creer un alias global apres la fin du bloc [PPLX_GEO_DETAIL_V1]
        end_marker = "/* === END [PPLX_GEO_DETAIL_V1] === */"
        if end_marker in new_src:
            alias = (
                f"\n\n/* === {MARKER} alias openGeoRiskDetail -> pplxGeoDetailOpen === */\n"
                "window.openGeoRiskDetail = function(riskId, riskTitle) {\n"
                "  if (typeof window.pplxGeoDetailOpen === 'function') {\n"
                "    return window.pplxGeoDetailOpen(riskId, riskTitle);\n"
                "  }\n"
                "  console.warn('[openGeoRiskDetail] pplxGeoDetailOpen indisponible');\n"
                "};\n"
            )
            new_src = new_src.replace(end_marker, end_marker + alias, 1)
            log("Alias openGeoRiskDetail -> pplxGeoDetailOpen cree")
        else:
            log("AVERT: end marker introuvable, alias non cree")
    elif has_open_geo:
        log("openGeoRiskDetail deja defini - rien a faire")
    else:
        log("AVERT: ni openGeoRiskDetail ni pplxGeoDetailOpen trouves")

    # ---------------------------------------------------------------
    # 3. Validation
    # ---------------------------------------------------------------
    if MARKER not in new_src:
        log("ERREUR: marqueur non insere")
        sys.exit(3)

    # Compter le early-return inserer
    if "return; // [PPLX_GEO_INJECT_DISABLED_V1]" not in new_src:
        log("ERREUR: early-return non insere")
        sys.exit(4)

    APP_JS.write_text(new_src, encoding="utf-8")
    log(f"OK - app.js patche ({len(src)} -> {len(new_src)} chars)")
    log("")
    log("ACTION:")
    log("  1. Hard refresh navigateur: Ctrl+Shift+F5")
    log("  2. Onglet Macro US -> Risques majeurs")
    log("  3. Verifier : 1 SEUL bouton 'Voir l'article complet' par carte (stylise)")

if __name__ == "__main__":
    main()
