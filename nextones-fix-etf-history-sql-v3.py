# -*- coding: utf-8 -*-
"""
[FIX_ETF_HISTORY_SQL_V3]
Restaure depuis le backup pre-patch (.bak-*-fix-etf-sql), puis remplace UNIQUEMENT la requete SQL.
Pas de marker inline. Validation syntaxe stricte.
"""
import re, shutil, datetime, ast, py_compile
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")

NEW_SQL = (
    '"SELECT p.date, p.close FROM prices p '
    'JOIN instruments i ON i.id = p.instrument_id '
    "WHERE UPPER(i.ticker) = UPPER(?) AND p.date >= date('now', ?) "
    'ORDER BY p.date;"'
)

def main():
    backups = sorted(AGENT.parent.glob("universe_expansion_agent.py.bak-*-fix-etf-sql"))
    if not backups:
        print("[ERR] aucun backup .bak-*-fix-etf-sql"); return
    src = backups[-1]
    print(f"[OK] base: {src.name}")

    raw = src.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    OLD_VARIANTS = [
        '"SELECT date, close FROM prices WHERE ticker = ? AND date >= date(\'now\', ?) ORDER BY date;"',
    ]
    # Cherche aussi via regex pour variantes
    m = re.search(r'"SELECT date, close FROM prices WHERE ticker[^"]*"', txt)
    if m and m.group(0) not in OLD_VARIANTS:
        OLD_VARIANTS.append(m.group(0))

    replaced = False
    for old in OLD_VARIANTS:
        if old in txt:
            txt = txt.replace(old, NEW_SQL, 1)
            print(f"[OK] requete remplacee: {old[:80]}...")
            replaced = True
            break

    if not replaced:
        print("[ERR] ancienne requete non trouvee dans le backup"); return

    # Validation syntaxe
    try:
        ast.parse(txt)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR SYNTAX] {e}"); return

    # Backup courant
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = AGENT.with_suffix(f".py.bak-{ts}-pre-v3")
    shutil.copy2(AGENT, bak)
    print(f"[BAK] {bak.name}")

    AGENT.write_bytes(txt.encode('utf-8'))

    try:
        py_compile.compile(str(AGENT), doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR py_compile] {e}"); return

    # Verif que p.ticker n'existe plus
    if 'p.ticker' in txt or "WHERE ticker = ?" in txt:
        print("[WARN] residus :")
        for kw in ['p.ticker', 'WHERE ticker = ?']:
            for m in re.finditer(re.escape(kw), txt):
                ln = txt[:m.start()].count('\n') + 1
                print(f"  L{ln}: {kw}")
    else:
        print("[OK] aucun residu p.ticker / WHERE ticker = ?")

    # Affiche les 10 lignes autour de fetch_etf_history pour controle visuel
    print()
    print("Verif visuelle (15 lignes autour de fetch_etf_history) :")
    print("-" * 60)
    lines = txt.splitlines()
    idx = next((i for i, ln in enumerate(lines, 1) if 'def fetch_etf_history' in ln), None)
    if idx:
        for i in range(max(1, idx-1), min(len(lines), idx+20)):
            print(f"  L{i:4d}: {lines[i-1]}")
    print("-" * 60)
    print()
    print("Relance : py -3.13 .\\nextones-diag-scan-empty.py")

if __name__ == "__main__":
    main()
