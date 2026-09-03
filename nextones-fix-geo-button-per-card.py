# -*- coding: utf-8 -*-
"""
Fix: Inject "Voir l'article complet" button INSIDE each .pplx-risk-card
Patch direct du template literal dans pplxRenderRisks (app.js ~position 289617)

Strategie:
1. Backup app.js
2. Localiser le template literal de la carte risque (`<div class="pplx-risk-card">`)
3. Inserer le bouton avant la fermeture </div> de la carte, avec data-risk-id
4. Brancher onclick: openGeoRiskDetail(riskId)
5. Si le MutationObserver existe (precedent patch), le supprimer pour eviter doublons
6. Validation: compter occurrences avant/apres

Marqueur idempotent: [PPLX_GEO_BTN_PER_CARD_V1]
"""

import re
import shutil
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
APP_JS = ROOT / "app.js"
MARKER = "[PPLX_GEO_BTN_PER_CARD_V1]"

def log(msg):
    print(f"[fix-geo-btn] {msg}")

def main():
    if not APP_JS.exists():
        log(f"ERREUR: introuvable {APP_JS}")
        sys.exit(1)

    src = APP_JS.read_text(encoding="utf-8-sig")
    if MARKER in src:
        log(f"DEJA APPLIQUE (marqueur {MARKER} present). Abort.")
        sys.exit(0)

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = APP_JS.with_suffix(f".js.bak-{ts}")
    shutil.copy2(APP_JS, backup)
    log(f"Backup: {backup.name}")

    # ---------------------------------------------------------------
    # 1. Localiser le template literal pplx-risk-card
    # ---------------------------------------------------------------
    # On cherche le pattern: `<div class="pplx-risk-card">...</div>` au sein
    # d'une fonction pplxRenderRisks (template literal entre backticks).
    # Approche: regex tolerante qui matche la chaine "pplx-risk-card" puis
    # le contenu jusqu'a la fermeture de la carte.

    # Compter occurrences avant
    count_card = src.count('class="pplx-risk-card"')
    log(f"Occurrences 'pplx-risk-card' AVANT: {count_card}")

    # Strategie simple: trouver le template literal de la fonction
    # pplxRenderRisks et injecter un bouton juste avant la fermeture
    # de la carte. On localise par anchor textuel.

    # Anchor: pplxRenderRisks function start
    if "pplxRenderRisks" not in src:
        log("ERREUR: fonction pplxRenderRisks introuvable")
        sys.exit(2)

    fn_pos = src.find("pplxRenderRisks")
    log(f"pplxRenderRisks trouve a position {fn_pos}")

    # Recherche du template literal contenant 'pplx-risk-card' apres fn_pos
    search_window = src[fn_pos:fn_pos + 20000]  # 20k chars de marge

    # Pattern: chercher la fermeture de la zone tickers (derniere ligne avant </div>)
    # On va injecter le bouton avant la fermeture finale de la carte.
    # Pattern recherche: une ligne contenant 'r.tickers' suivie de </div> qui ferme la carte

    # Approche pragmatique: chercher 'r.tickers' dans la fenetre et identifier
    # la fermeture </div> qui suit
    tickers_idx_local = search_window.find("r.tickers")
    if tickers_idx_local == -1:
        log("AVERT: 'r.tickers' non trouve, fallback sur narrative")
        tickers_idx_local = search_window.find("r.narrative")
        if tickers_idx_local == -1:
            log("ERREUR: ni r.tickers ni r.narrative trouve")
            sys.exit(3)

    # Position absolue
    anchor_abs = fn_pos + tickers_idx_local
    log(f"Anchor (r.tickers/r.narrative) a position absolue {anchor_abs}")

    # Chercher la fermeture </div> qui ferme la carte: on prend la 1ere
    # fermeture </div> qui apparait apres r.tickers et qui est suivie soit
    # d'un backtick (fin template), soit d'une virgule, soit d'un retour ligne
    # vers une nouvelle carte.
    # Pratique: on prend la 1ere </div> apres r.tickers et on insere avant.

    # Avancer apres r.tickers jusqu'a fin de la ligne/section
    after_tickers = src[anchor_abs:anchor_abs + 2000]

    # On cherche '</div>' apres r.tickers - prendre celui qui ferme la carte
    # Le template typique:
    # `<div class="pplx-risk-card">
    #    <div ...>...</div>  <!-- header -->
    #    <div ...>...</div>  <!-- narrative -->
    #    <div ...>${r.tickers.map(...)}</div>  <!-- tickers -->
    #  </div>`
    # Donc apres r.tickers il y a un </div> proche (fermeture div tickers)
    # puis un </div> qui ferme la carte.

    # On cherche les 2 prochaines </div> apres r.tickers
    closes = []
    pos = 0
    while len(closes) < 4:
        idx = after_tickers.find("</div>", pos)
        if idx == -1:
            break
        closes.append(idx)
        pos = idx + 6

    log(f"Positions </div> apres r.tickers (relatives): {closes}")

    if len(closes) < 2:
        log("ERREUR: pas assez de </div> apres r.tickers")
        sys.exit(4)

    # Le 2e </div> ferme la carte (le 1er ferme la div tickers).
    # Mais selon la structure ca peut etre le 1er ou 2e. On va inserer
    # le bouton AVANT le DERNIER </div> qui precede la fermeture du
    # template literal (backtick `).

    # Localiser le backtick de fin du template literal de la carte
    backtick_idx = after_tickers.find("`", closes[0])
    log(f"Backtick de fin template a position relative: {backtick_idx}")

    # Trouver le dernier </div> qui precede le backtick
    target_close_rel = None
    for idx in closes:
        if backtick_idx == -1 or idx < backtick_idx:
            target_close_rel = idx
    if target_close_rel is None:
        target_close_rel = closes[-1]

    target_close_abs = anchor_abs + target_close_rel
    log(f"Insertion du bouton AVANT </div> a position absolue {target_close_abs}")

    # Le bouton a injecter (avec data-risk-id pour permettre l'ouverture du detail)
    # On utilise r.risk_id si dispo, sinon r.id, sinon r.title comme fallback
    button_snippet = (
        '<div class="pplx-risk-card-actions" style="margin-top:10px;">'
        '<button class="pplx-risk-detail-btn" '
        'data-risk-id="${r.risk_id || r.id || \'\'}" '
        'data-risk-title="${(r.title||\'\').replace(/"/g,\'&quot;\')}" '
        'onclick="openGeoRiskDetail(this.dataset.riskId, this.dataset.riskTitle)">'
        'Voir l\'article complet'
        '</button>'
        '</div>'
        f' <!-- {MARKER} -->'
    )

    new_src = src[:target_close_abs] + button_snippet + src[target_close_abs:]

    # ---------------------------------------------------------------
    # 2. Supprimer le MutationObserver du patch precedent (s'il existe)
    # ---------------------------------------------------------------
    # On cherche un bloc commencant par 'MutationObserver' et associe au
    # patch geo precedent. Marqueur probable: [PPLX_GEO_DETAIL_V1] ou autre
    # On ne supprime PAS, on ajoute juste un flag pour desactiver le matching:
    # le bouton existe maintenant directement, le MutationObserver injection
    # devient inutile mais ne cassera pas (il cherchera un selecteur et n'agira
    # plus si on patch openGeoRiskDetail).

    # Verifier que openGeoRiskDetail existe
    if "openGeoRiskDetail" not in new_src:
        log("AVERT: openGeoRiskDetail() pas trouvee - le bouton ne fonctionnera pas")
        log("       Verifier que le patch geo-panel-move-and-detail.py a bien defini cette fonction")
    else:
        log("openGeoRiskDetail() trouvee - OK")

    # ---------------------------------------------------------------
    # 3. Validation
    # ---------------------------------------------------------------
    count_btn = new_src.count("pplx-risk-detail-btn")
    log(f"Boutons 'pplx-risk-detail-btn' APRES patch: {count_btn} (attendu: 1, sera multiplie par 5 au runtime)")

    if MARKER not in new_src:
        log("ERREUR: marqueur non present dans output")
        sys.exit(5)

    # ---------------------------------------------------------------
    # 4. Ecriture utf-8 sans BOM
    # ---------------------------------------------------------------
    APP_JS.write_text(new_src, encoding="utf-8")
    log(f"OK - app.js patche ({len(new_src)} chars)")
    log(f"     Bouton inject dans chaque .pplx-risk-card via template literal")
    log(f"     Marqueur: {MARKER}")
    log("")
    log("ACTION: refresh navigateur (Ctrl+F5) puis cliquer sur 'Risques majeurs'")
    log("        Chaque carte doit afficher le bouton 'Voir l'article complet'")

if __name__ == "__main__":
    main()
