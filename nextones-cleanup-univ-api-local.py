# -*- coding: utf-8 -*-
"""
[CLEANUP_UNIV_API_LOCAL_V1]
Supprime proprement la fonction async function api(path, opts){...} restante
dans le bloc [UI_UNIVERSE_V2_*]. Utilise un parser a accolades equilibrees
(plus robuste que regex).
Idempotent via marker [UI_UNIV_CLEANUP_V1_OK].
"""
import re, shutil, datetime
from pathlib import Path

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
MARK_OK = "[UI_UNIV_CLEANUP_V1_OK]"

def find_func_end(txt, start_idx):
    """A partir du { d'ouverture (cherche depuis start_idx), trouve le } equilibre."""
    # cherche le premier {
    i = txt.find('{', start_idx)
    if i < 0: return -1
    depth = 0
    while i < len(txt):
        c = txt[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1

def main():
    raw = HTML.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK_OK in txt:
        print(f"[SKIP] deja {MARK_OK}"); return

    m = re.search(r'\[UI_UNIVERSE_V2_BEGIN\].*?\[UI_UNIVERSE_V2_END\]', txt, re.DOTALL)
    if not m:
        print("[ERR] bloc introuvable"); return

    block = m.group(0)
    block_start_in_file = m.start()

    # Cherche debut de "async function api(" dans le bloc
    sig = re.search(r'async\s+function\s+api\s*\(', block)
    if not sig:
        print("[INFO] async function api(...) deja absente, rien a nettoyer")
        # ajoute quand meme le marker pour rendre idempotent
        new_block = block.replace('[UI_UNIVERSE_V2_BEGIN]',
                                  f'[UI_UNIVERSE_V2_BEGIN] {MARK_OK}', 1)
        if new_block != block:
            ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
            bak = HTML.with_suffix(f".html.bak-{ts}-univ-cleanup-noop")
            shutil.copy2(HTML, bak)
            HTML.write_bytes((txt[:m.start()] + new_block + txt[m.end():]).encode('utf-8'))
            print(f"[OK] marker ajoute, backup {bak.name}")
        return

    fn_start = sig.start()
    fn_end = find_func_end(block, sig.end())
    if fn_end < 0:
        print("[ERR] accolade fermante introuvable"); return

    fn_body = block[fn_start:fn_end]
    print(f"[OK] api() locale trouvee : {len(fn_body)} chars (offset {fn_start}..{fn_end})")
    print("--- bloc supprime (premieres 200 chars) ---")
    print(fn_body[:200])
    print("...")
    print(fn_body[-100:])
    print("---")

    # Verifie qu'on a pas de window.apiFetch DANS la fonction (sinon mauvais match)
    if 'window.apiFetch' in fn_body:
        print("[WARN] window.apiFetch present DANS le corps a supprimer — possible faux positif")
        print("Verif manuelle requise, abandon.")
        return

    # Backup
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = HTML.with_suffix(f".html.bak-{ts}-univ-cleanup-v1")
    shutil.copy2(HTML, bak)

    # Construit nouveau bloc : retire la fonction + ajoute marker
    new_block = block[:fn_start] + block[fn_end:]
    new_block = new_block.replace('[UI_UNIVERSE_V2_BEGIN]',
                                   f'[UI_UNIVERSE_V2_BEGIN] {MARK_OK}', 1)

    # Verifie les balises critiques
    for tag in ['<section id="card-universe-candidates"', '</section>',
                'loadCandidates', 'btn-univ-scan', 'window.apiFetch']:
        a, b = block.count(tag), new_block.count(tag)
        if tag == 'window.apiFetch':
            if b < 1:
                print(f"[ERR] window.apiFetch absent apres patch ({b})"); return
        elif a != b:
            print(f"[ERR] tag {tag!r}: avant={a} apres={b}, abandon"); return

    new_txt = txt[:m.start()] + new_block + txt[m.end():]
    HTML.write_bytes(new_txt.encode('utf-8'))
    print(f"[OK] backup {bak.name}")
    print(f"[OK] {len(block) - len(new_block)} chars supprimes")
    print(f"[OK] window.apiFetch occurrences dans le bloc : {new_block.count('window.apiFetch')}")
    print()
    print("=" * 60)
    print("Recharge avec Ctrl+F5 et teste la carte.")
    print("=" * 60)

if __name__ == "__main__":
    main()
