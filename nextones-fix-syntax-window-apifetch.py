# -*- coding: utf-8 -*-
"""
[FIX_SYNTAX_WINDOW_APIFETCH_V1]
Supprime la declaration invalide :
  async function window.apiFetch(path, opts){
    ... corps ...
  }
laissee par le patch precedent dans le bloc [UI_UNIVERSE_V2_*].

Strategie : trouve la ligne "async function window.apiFetch(" et supprime jusqu'a
l'accolade fermante equilibree.
Idempotent via marker [FIX_SYNTAX_V1_OK].
"""
import re, shutil, datetime
from pathlib import Path

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
MARK_OK = "[FIX_SYNTAX_V1_OK]"

def find_func_end(txt, after_idx):
    i = txt.find('{', after_idx)
    if i < 0: return -1
    depth = 0
    while i < len(txt):
        c = txt[i]
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return i + 1
        i += 1
    return -1

def main():
    raw = HTML.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK_OK in txt:
        print(f"[SKIP] {MARK_OK} present"); return

    # Cherche la declaration invalide
    sig = re.search(r'async\s+function\s+window\.apiFetch\s*\(', txt)
    if not sig:
        print("[INFO] declaration invalide deja absente")
        return

    print(f"[OK] declaration invalide trouvee a offset {sig.start()}, ligne {txt[:sig.start()].count(chr(10))+1}")

    fn_end = find_func_end(txt, sig.end())
    if fn_end < 0:
        print("[ERR] accolade fermante introuvable"); return

    fn_body = txt[sig.start():fn_end]
    print(f"  Bloc a supprimer : {len(fn_body)} chars, {fn_body.count(chr(10))+1} lignes")
    print("--- contenu ---")
    print(fn_body)
    print("--- fin ---")

    # Garde-fou : doit contenir 'fetch' et 'getToken' (le residu attendu)
    if 'fetch(' not in fn_body or 'getToken' not in fn_body:
        print("[WARN] contenu inattendu, abandon par securite")
        return

    # Backup
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = HTML.with_suffix(f".html.bak-{ts}-fix-syntax-v1")
    shutil.copy2(HTML, bak)
    print(f"[BACKUP] {bak.name}")

    # Supprime (en preservant l'indentation/saut de ligne propre)
    # On enleve aussi le saut de ligne suivant si present
    end_with_nl = fn_end
    if end_with_nl < len(txt) and txt[end_with_nl] == '\n':
        end_with_nl += 1

    new_txt = txt[:sig.start()] + txt[end_with_nl:]

    # Ajoute marker juste apres [UI_UNIVERSE_V2_BEGIN]
    new_txt = new_txt.replace('[UI_UNIVERSE_V2_BEGIN]',
                               f'[UI_UNIVERSE_V2_BEGIN] {MARK_OK}', 1)

    # Verifications :
    # 1) plus de "async function window.apiFetch"
    if 'async function window.apiFetch' in new_txt:
        print("[ERR] residu encore present, abandon"); return
    # 2) appels window.apiFetch( restent presents
    n_calls = new_txt.count('window.apiFetch(')
    print(f"  Appels 'window.apiFetch(' restants : {n_calls}")
    if n_calls < 4:
        print("[WARN] trop peu d'appels restants"); 
    # 3) balises critiques inchangees
    for tag in ['<section id="card-universe-candidates"',
                'loadCandidates', 'btn-univ-scan', 'function scorePill']:
        a, b = txt.count(tag), new_txt.count(tag)
        if a != b:
            print(f"[ERR] tag {tag!r}: avant={a} apres={b}, abandon"); return

    HTML.write_bytes(new_txt.encode('utf-8'))
    print(f"[OK] ecrit ({len(txt)} -> {len(new_txt)} chars)")
    print()
    print("=" * 60)
    print("Ctrl+F5 dans le navigateur, puis verifie la console (F12).")
    print("La table doit afficher 'Aucun candidat en attente.'")
    print("=" * 60)

if __name__ == "__main__":
    main()
