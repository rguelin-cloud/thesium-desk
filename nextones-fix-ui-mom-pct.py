# -*- coding: utf-8 -*-
"""
[FIX_UI_MOM_PCT_V1]
Affiche MOM 12-1 en pourcentage dans la carte 'Univers - Candidats'.
Avant : 14.201  (ratio brut, illisible)
Apres : 1420.1%

Patch dans index.html :
  ${fmt(c.momentum_12m_minus_1m, 3)}
  -> ${fmt(c.momentum_12m_minus_1m * 100, 1)}%

Idempotent via marker [FIX_UI_MOM_PCT_V1].
"""
import re
import shutil
import datetime
from pathlib import Path

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
MARK = "/* [FIX_UI_MOM_PCT_V1] */"

OLD = "${fmt(c.momentum_12m_minus_1m, 3)}"
NEW = "${fmt(c.momentum_12m_minus_1m * 100, 1)}%"


def main():
    if not HTML.exists():
        print(f"[ERR] {HTML} introuvable")
        return

    raw = HTML.read_bytes()
    bom = b"\xef\xbb\xbf"
    has_bom = raw.startswith(bom)
    if has_bom:
        raw = raw[3:]
    txt = raw.decode("utf-8", errors="replace")

    if MARK in txt:
        print(f"[SKIP] {MARK} deja present, rien a faire")
        return

    # Compte occurrences AVANT
    n_old = txt.count(OLD)
    print(f"[INFO] {n_old} occurrence(s) trouvee(s) de OLD")

    if n_old == 0:
        # Tentative avec variante d'espaces
        OLD2 = "fmt(c.momentum_12m_minus_1m, 3)"
        n_old2 = txt.count(OLD2)
        print(f"[INFO] variante sans accolades : {n_old2} occurrence(s)")
        if n_old2 == 0:
            print("[ERR] aucun pattern reconnu, abandon")
            return
        new_txt = txt.replace(OLD2, "fmt(c.momentum_12m_minus_1m * 100, 1)")
        # Mais sans % suffix, on injecte un wrapping
        # Plus simple : on cherche le td environnant
        # Pour rester safe : on n'utilise PAS cette branche, et on previent
        print("[WARN] pattern alternatif detecte sans accolades complets, abandon par securite")
        return
    else:
        new_txt = txt.replace(OLD, NEW)

    # Verif nb remplacements
    n_replaced = new_txt.count(NEW)
    n_old_remaining = new_txt.count(OLD)
    print(f"[OK] remplacements : {n_replaced}, OLD restants : {n_old_remaining}")
    if n_replaced != n_old or n_old_remaining > 0:
        print("[ERR] count remplacements incoherent, abandon")
        return

    # Inserer marker en fin de fichier (commentaire HTML)
    if not new_txt.endswith("\n"):
        new_txt += "\n"
    new_txt += f"<!-- {MARK.strip('/*').strip()} -->\n"

    # Backup
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(f".html.bak-{ts}-pre-mom-pct")
    shutil.copy2(HTML, bak)
    print(f"[BAK] {bak.name}")

    # Ecriture (utf-8 sans BOM, conforme aux conventions du projet)
    HTML.write_bytes(new_txt.encode("utf-8"))
    print("[OK] index.html ecrit (utf-8 sans BOM)")

    print()
    print("Recharge l'UI avec Ctrl+F5 pour voir MOM 12-1 en pourcentage.")


if __name__ == "__main__":
    main()
