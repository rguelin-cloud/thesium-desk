# -*- coding: utf-8 -*-
"""
[FIX_CAP_PCT_DISPLAY_V1]
Corrige l'affichage du Cap % dans la carte Univers Candidats.
L'agent stocke des fractions (0.05 = 5%) mais le JS affiche brut.

Patch : remplace `fmt(c.suggested_cap_pct, 1)` par `fmt((c.suggested_cap_pct||0)*100, 1)+'%'`
ou variante similaire.

Idempotent via marker [FIX_CAP_PCT_V1].
Backup horodate.
"""
import re, shutil, datetime
from pathlib import Path

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
MARK = "[FIX_CAP_PCT_V1]"

def main():
    raw = HTML.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK in txt:
        print(f"[SKIP] {MARK} deja present"); return

    OLD = '${fmt(c.suggested_cap_pct, 1)}'
    NEW = '${fmt((c.suggested_cap_pct||0)*100, 1)}%'

    if OLD not in txt:
        print(f"[ERR] motif introuvable: {OLD}")
        # cherche variantes
        for m in re.finditer(r'fmt\(\s*c\.suggested_cap_pct[^)]*\)', txt):
            line_no = txt[:m.start()].count('\n') + 1
            print(f"  variante L{line_no}: {m.group(0)}")
        return

    n_before = txt.count(OLD)
    txt = txt.replace(OLD, NEW, 1)
    print(f"[OK] {n_before} occurrence(s) remplacees")

    # Ajoute marker dans le bloc UI_UNIVERSE_V2
    txt = txt.replace('[UI_UNIVERSE_V2_BEGIN]',
                       f'[UI_UNIVERSE_V2_BEGIN] {MARK}', 1)

    # Backup
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = HTML.with_suffix(f".html.bak-{ts}-fix-cap-pct")
    shutil.copy2(HTML, bak)
    print(f"[BAK] {bak.name}")

    HTML.write_bytes(txt.encode('utf-8'))
    print(f"[OK] ecrit")
    print()
    print("Ctrl+F5 dans le navigateur — la colonne CAP % doit afficher 5.0% / 3.0%")

if __name__ == "__main__":
    main()
