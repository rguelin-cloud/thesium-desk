# -*- coding: utf-8 -*-
"""
[FIX_UI_UNIV_APIFETCH_V1]
Remplace dans le bloc [UI_UNIVERSE_V2_*] de index.html :
- getToken() + api() locaux -> window.apiFetch (wrapper global de app.js)
- Tous les appels api(...) -> apiFetch(...)

Idempotent (skip si marker [UI_UNIV_APIFETCH_V1_OK] deja present).
Backup horodate.
"""
import re, shutil, datetime
from pathlib import Path

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
MARK_OK = "[UI_UNIV_APIFETCH_V1_OK]"

def main():
    if not HTML.exists():
        print(f"[ERR] {HTML} introuvable"); return

    raw = HTML.read_bytes()
    # decode utf-8 (BOM-safe)
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK_OK in txt:
        print(f"[SKIP] deja patche ({MARK_OK} present)")
        return

    m = re.search(r'\[UI_UNIVERSE_V2_BEGIN\].*?\[UI_UNIVERSE_V2_END\]', txt, re.DOTALL)
    if not m:
        print("[ERR] bloc [UI_UNIVERSE_V2_*] introuvable")
        return

    block = m.group(0)
    print(f"[OK] bloc trouve : {len(block)} chars, lignes {txt[:m.start()].count(chr(10))+1}..{txt[:m.end()].count(chr(10))+1}")

    # Backup
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = HTML.with_suffix(f".html.bak-{ts}-univ-apifetch-v1")
    shutil.copy2(HTML, bak)
    print(f"[BACKUP] {bak.name}")

    new_block = block

    # 1) Supprime getToken() complete
    new_block, n1 = re.subn(
        r'function\s+getToken\s*\(\s*\)\s*\{[^}]*?\}\s*',
        '',
        new_block,
        count=1
    )
    print(f"  - getToken supprime : {n1}")

    # 2) Supprime api() complete (le wrapper local)
    new_block, n2 = re.subn(
        r'async\s+function\s+api\s*\([^)]*\)\s*\{[^}]*?return\s+r\.json\(\);\s*\}\s*',
        '',
        new_block,
        count=1
    )
    print(f"  - api() local supprime : {n2}")

    # 3) Remplace tous les appels api(...) par window.apiFetch(...)
    #    On cible les appels nus "api(" precedes par " await " ou "( " ou "= "
    #    Mais on evite de toucher "apiFetch" ou "_api"
    # Pattern : (?<![A-Za-z0-9_])api\(
    new_block, n3 = re.subn(
        r'(?<![A-Za-z0-9_])api\(',
        'window.apiFetch(',
        new_block
    )
    print(f"  - api(...) -> window.apiFetch(...) : {n3} remplacements")

    # 4) Ajoute le marker OK juste apres [UI_UNIVERSE_V2_BEGIN]
    new_block = new_block.replace(
        '[UI_UNIVERSE_V2_BEGIN]',
        f'[UI_UNIVERSE_V2_BEGIN] {MARK_OK}',
        1
    )

    if new_block == block:
        print("[WARN] aucun changement effectif applique")
        return

    new_txt = txt[:m.start()] + new_block + txt[m.end():]

    # Verifie qu'on n'a pas perdu de balise importante
    for tag in ['<section id="card-universe-candidates"', '</section>', 'loadCandidates', 'btn-univ-scan']:
        a, b = block.count(tag), new_block.count(tag)
        if a != b:
            print(f"[ERR] tag {tag!r} : avant={a} apres={b} — abandon")
            return

    # Ecriture utf-8 sans BOM
    HTML.write_bytes(new_txt.encode('utf-8'))
    print(f"[OK] ecrit {HTML} ({len(new_txt)} chars)")
    print(f"[OK] backup : {bak.name}")
    print()
    print("=" * 60)
    print("PROCHAINE ETAPE :")
    print("  1) Recharge la page (Ctrl+F5)")
    print("  2) Connecte-toi si besoin (l'app appelle saveSession)")
    print("  3) La carte Univers Candidats devrait charger sans 401")
    print("=" * 60)

if __name__ == "__main__":
    main()
