# -*- coding: utf-8 -*-
"""
[FIX_ETF_HISTORY_SQL_V2]
Restaure depuis le backup fix-etf-sql, puis re-patche proprement :
- SQL fetch_etf_history : remplace par version JOIN instruments, en string ONE-LINE
- Marker en commentaire SEPARE (ligne dediee, pas inline)

Idempotent via marker [FIX_ETF_SQL_V2].
"""
import re, shutil, datetime
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
MARK = "[FIX_ETF_SQL_V2]"

NEW_SQL = (
    '"SELECT p.date, p.close FROM prices p '
    'JOIN instruments i ON i.id = p.instrument_id '
    "WHERE UPPER(i.ticker) = UPPER(?) AND p.date >= date('now', ?) "
    'ORDER BY p.date;"'
)

def main():
    # 1) Cherche le backup le plus recent fix-etf-sql
    backups = sorted(AGENT.parent.glob("universe_expansion_agent.py.bak-*-fix-etf-sql"))
    if not backups:
        print("[ERR] aucun backup fix-etf-sql trouve, abandon")
        return
    last = backups[-1]
    print(f"[OK] Restaure depuis : {last.name}")

    raw = last.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK in txt:
        print(f"[SKIP] {MARK} deja present")
        return

    # 2) L'ancienne requete (dans le backup, donc encore avec p.ticker)
    OLD = '"SELECT date, close FROM prices WHERE ticker = ? AND date >= date(\'now\', ?) ORDER BY date;"'
    if OLD not in txt:
        # cherche variante
        m = re.search(r'"SELECT date, close FROM prices WHERE ticker[^"]*"', txt)
        if not m:
            print("[ERR] ancienne requete introuvable, abandon")
            return
        OLD = m.group(0)
        print(f"[INFO] requete trouvee : {OLD!r}")

    # 3) Replace
    txt2 = txt.replace(OLD, NEW_SQL, 1)
    if txt2 == txt:
        print("[ERR] aucun remplacement effectue"); return

    # 4) Ajoute le marker sur ligne SEPAREE juste apres la signature fetch_etf_history
    sig = re.search(r'(def\s+fetch_etf_history[^:]+:\s*\n\s*"""[^"]+"""\s*\n)', txt2)
    if not sig:
        print("[ERR] signature non trouvee pour marker"); return
    indent = '    '  # 4 espaces (fonction top-level)
    marker_line = f'{indent}# {MARK}\n'
    txt2 = txt2[:sig.end()] + marker_line + txt2[sig.end():]

    # 5) Verifs
    if 'p.ticker' in txt2 or 'WHERE ticker =' in txt2:
        print("[WARN] ancien SQL encore present quelque part :")
        for m in re.finditer(r'p\.ticker|WHERE ticker =', txt2):
            line_no = txt2[:m.start()].count('\n') + 1
            print(f"  L{line_no}: {txt2[txt2.rfind(chr(10), 0, m.start())+1:txt2.find(chr(10), m.end())][:120]}")

    # 6) Syntax check
    import ast
    try:
        ast.parse(txt2)
        print("[OK] syntaxe valide")
    except SyntaxError as e:
        print(f"[ERR SYNTAX] {e}")
        return

    # 7) Backup courant + ecrit
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = AGENT.with_suffix(f".py.bak-{ts}-fix-etf-sql-v2-pre")
    shutil.copy2(AGENT, bak)
    print(f"[BACKUP courant] {bak.name}")

    AGENT.write_bytes(txt2.encode('utf-8'))
    print(f"[OK] {AGENT.name} ecrit ({len(txt2)} chars)")

    # Verifie syntaxe sur le fichier ecrit
    import py_compile
    try:
        py_compile.compile(str(AGENT), doraise=True)
        print("[OK] py_compile valide")
    except py_compile.PyCompileError as e:
        print(f"[ERR py_compile] {e}")
        return

    print()
    print("=" * 60)
    print("Relance le diag :")
    print("  py -3.13 .\\nextones-diag-scan-empty.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
