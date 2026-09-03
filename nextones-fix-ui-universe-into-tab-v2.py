# -*- coding: utf-8 -*-
"""
[FIX_UI_UNIVERSE_INTO_TAB_V2]
Version corrigee : accepte n'importe quelle balise (div, section, main, article)
pour tab-today.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-fix-ui-universe-into-tab-v2.py
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


def find_matching_close_tag(txt: str, tag: str, open_pos: int) -> int:
    """Trouve la position du </tag> qui matche le tag ouvert a open_pos.
    Retourne l'index du < dans </tag>, ou -1."""
    open_pat  = re.compile(rf"<{tag}\b[^>]*>", re.IGNORECASE)
    close_pat = re.compile(rf"</{tag}\s*>",   re.IGNORECASE)

    # depth = 1 (on est juste apres le tag ouvrant initial)
    # avancer en trouvant l'index du < pour la prochaine occurrence
    pos = open_pos
    depth = 1
    while pos < len(txt):
        nxt_open = open_pat.search(txt, pos)
        nxt_close = close_pat.search(txt, pos)
        if not nxt_close:
            return -1
        if nxt_open and nxt_open.start() < nxt_close.start():
            depth += 1
            pos = nxt_open.end()
        else:
            depth -= 1
            if depth == 0:
                return nxt_close.start()
            pos = nxt_close.end()
    return -1


def find_tab_today_container(txt: str) -> tuple[str, int, int] | None:
    """Cherche n'importe quelle balise contenant id="tab-today".
    Retourne (tag, open_start, close_start_of_</tag>)."""
    # Match <TAG ... id="tab-today" ... >
    pat = re.compile(
        r'<(div|section|main|article|aside)\b[^>]*\bid\s*=\s*["\']tab-today["\'][^>]*>',
        re.IGNORECASE,
    )
    m = pat.search(txt)
    if not m:
        return None
    tag = m.group(1).lower()
    open_start = m.start()
    open_end = m.end()
    close_pos = find_matching_close_tag(txt, tag, open_end)
    if close_pos == -1:
        return None
    return (tag, open_start, close_pos)


def main() -> int:
    if not HTML.exists():
        print(f"[FAIL] {HTML} introuvable.")
        return 1

    txt = HTML.read_text(encoding="utf-8", errors="replace")
    print(f"[INFO] {HTML.name}: {len(txt)} chars")

    section("1) Extraction du bloc V2 actuel")
    if MARK_BEGIN not in txt or MARK_END not in txt:
        print("[FAIL] markers V2 introuvables. Relance d'abord nextones-ui-universe-candidates-card-v2.py")
        return 2
    start = txt.index(MARK_BEGIN)
    end = txt.index(MARK_END, start) + len(MARK_END)
    block = txt[start:end]
    line_begin = txt[:start].count("\n") + 1
    line_end = txt[:end].count("\n") + 1
    print(f"[OK] bloc trouve: {len(block)} chars, lignes {line_begin}..{line_end}")

    section("2) Localisation de tab-today (toutes balises)")
    found = find_tab_today_container(txt)
    if not found:
        print("[FAIL] aucun conteneur avec id=tab-today trouve.")
        # debug: cherche toutes les occurrences brutes
        for m in re.finditer(r'id\s*=\s*["\']tab-today["\']', txt):
            l = txt[:m.start()].count("\n") + 1
            ctx = txt[max(0, m.start()-80):m.end()+20].replace("\n", " | ")
            print(f"  L{l}: ...{ctx}...")
        return 3
    tag, today_open_pos, today_close = found
    line_open = txt[:today_open_pos].count("\n") + 1
    line_close = txt[:today_close].count("\n") + 1
    print(f"[OK] <{tag} id=tab-today> ouvert L{line_open}, ferme L{line_close}")

    if today_open_pos < start < today_close:
        print("[SKIP] le bloc V2 est deja a l'interieur de tab-today.")
        return 0

    section("3) Reinjection a la fin de tab-today")

    # Supprimer le bloc actuel
    txt2 = txt[:start] + txt[end:]
    if start < today_close:
        today_close_new = today_close - (end - start)
    else:
        today_close_new = today_close

    insertion = "\n" + block + "\n"
    new_txt = txt2[:today_close_new] + insertion + txt2[today_close_new:]

    new_v2_line = new_txt[:new_txt.index(MARK_BEGIN)].count("\n") + 1
    print(f"[INFO] nouvelle position: ligne {new_v2_line}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = HTML.with_suffix(f".html.bak-{ts}-ui-univ-into-tab-v2")
    shutil.copy2(HTML, bak)
    print(f"[BACKUP] {bak.name}")

    HTML.write_text(new_txt, encoding="utf-8")
    print(f"[OK] {HTML.name} patche.")

    section("4) Verification finale")
    found2 = find_tab_today_container(new_txt)
    new_v2_start = new_txt.index(MARK_BEGIN)
    if found2:
        _, t_open, t_close = found2
        if t_open < new_v2_start < t_close:
            print(f"[OK] bloc V2 est maintenant a l'interieur de tab-today.")
        else:
            print(f"[WARN] V2 hors tab-today: V2={new_v2_start}, today=[{t_open}..{t_close}]")

    print("\nFait :")
    print("  Ctrl+Shift+R sur l'onglet Today -> la carte 'Univers — Candidats'")
    print("  apparait en bas (apres Positions / Recent Activity).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
