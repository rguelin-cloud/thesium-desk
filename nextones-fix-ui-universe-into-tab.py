# -*- coding: utf-8 -*-
"""
[FIX_UI_UNIVERSE_INTO_TAB_V1]
Deplace la carte Universe Candidates a l'INTERIEUR du tab Today
(le marker V2 actuel est apres tous les tabs -> invisible).

Strategie:
  1) Extraire le bloc entre [UI_UNIVERSE_V2_BEGIN] et [UI_UNIVERSE_V2_END]
  2) Le supprimer de son emplacement actuel
  3) Le re-injecter a la FIN du contenu de <div id="tab-today">

Idempotent (detecte si la carte est deja dans tab-today).
Backup auto.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-fix-ui-universe-into-tab.py
"""
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = ROOT / "index.html"

MARK_BEGIN = "<!-- [UI_UNIVERSE_V2_BEGIN] -->"
MARK_END   = "<!-- [UI_UNIVERSE_V2_END] -->"


def section(t):
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


def find_matching_close_div(txt: str, open_pos: int) -> int:
    """A partir de la position d'un <div ...>, retourne l'index du </div> qui matche."""
    depth = 0
    i = open_pos
    n = len(txt)
    while i < n:
        # avancer
        next_open = txt.find("<div", i)
        next_close = txt.find("</div>", i)
        if next_close == -1:
            return -1
        if next_open != -1 and next_open < next_close:
            depth += 1
            i = next_open + 4
        else:
            depth -= 1
            i = next_close + len("</div>")
            if depth == 0:
                return next_close
    return -1


def main() -> int:
    if not HTML.exists():
        print(f"[FAIL] {HTML} introuvable.")
        return 1

    txt = HTML.read_text(encoding="utf-8", errors="replace")
    print(f"[INFO] {HTML.name}: {len(txt)} chars")

    # 1) Localiser le bloc V2 actuel
    section("1) Extraction du bloc V2 actuel")
    if MARK_BEGIN not in txt or MARK_END not in txt:
        print("[FAIL] markers V2 introuvables. Relance d'abord nextones-ui-universe-candidates-card-v2.py")
        return 2
    start = txt.index(MARK_BEGIN)
    end = txt.index(MARK_END, start) + len(MARK_END)
    block = txt[start:end]
    print(f"[OK] bloc trouve: {len(block)} chars, ligne {txt[:start].count(chr(10))+1}..{txt[:end].count(chr(10))+1}")

    # 2) Localiser <div id="tab-today" ...>
    section("2) Localisation de tab-today")
    m_today = re.search(r'<div[^>]+id\s*=\s*["\']tab-today["\'][^>]*>', txt)
    if not m_today:
        print("[FAIL] <div id=\"tab-today\"> introuvable.")
        return 3
    today_open_pos = m_today.start()
    today_open_end = m_today.end()
    today_close = find_matching_close_div(txt, today_open_pos)
    if today_close == -1:
        print("[FAIL] </div> matching pour tab-today introuvable.")
        return 4
    print(f"[OK] tab-today: lignes {txt[:today_open_pos].count(chr(10))+1}..{txt[:today_close].count(chr(10))+1}")

    # Check si bloc V2 est DEJA dans tab-today
    if today_open_pos < start < today_close:
        print("[SKIP] le bloc V2 est deja a l'interieur de tab-today.")
        return 0

    # 3) Calculer la nouvelle position avant </div> de tab-today
    section("3) Reinjection a la fin de tab-today")

    # Supprimer le bloc actuel
    txt2 = txt[:start] + txt[end:]
    # ajuster today_close si suppression avant
    if start < today_close:
        today_close_new = today_close - (end - start)
    else:
        today_close_new = today_close

    # Inserer juste AVANT </div> de tab-today
    # On veut une nouvelle ligne avant le marker
    insertion = "\n" + block + "\n"
    new_txt = txt2[:today_close_new] + insertion + txt2[today_close_new:]

    print(f"[INFO] nouvelle position: ligne {new_txt[:new_txt.index(MARK_BEGIN)].count(chr(10))+1}")

    # 4) Backup + write
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(f".html.bak-{ts}-ui-univ-into-tab")
    shutil.copy2(HTML, bak)
    print(f"[BACKUP] {bak.name}")

    HTML.write_text(new_txt, encoding="utf-8")
    print(f"[OK] {HTML.name} patche.")

    # 5) Verification
    section("4) Verification finale")
    new_v2_start = new_txt.index(MARK_BEGIN)
    new_today_match = re.search(r'<div[^>]+id\s*=\s*["\']tab-today["\'][^>]*>', new_txt)
    if new_today_match:
        new_today_open = new_today_match.start()
        new_today_close = find_matching_close_div(new_txt, new_today_open)
        if new_today_open < new_v2_start < new_today_close:
            print("[OK] bloc V2 est maintenant a l'interieur de tab-today.")
        else:
            print(f"[WARN] verification: V2={new_v2_start}, today=[{new_today_open}..{new_today_close}]")

    print("\nProchaine etape:")
    print("  1. F5 / Ctrl+Shift+R dans le navigateur (sur l'onglet Today)")
    print("  2. La carte 'Univers — Candidats' apparait en bas de Today")
    print("  3. Clique 'Lancer scan'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
