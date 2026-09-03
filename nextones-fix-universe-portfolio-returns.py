# -*- coding: utf-8 -*-
"""
[FIX_UNIV_PORTFOLIO_RETURNS_V1]
Reecrit la requete SQL de _existing_portfolio_returns dans universe_expansion_agent.py.

Probleme : la requete reference p.ticker mais la table prices n'a que instrument_id.
Solution : JOIN prices -> instruments (par instrument_id) -> portfolio_targets (par ticker).

Idempotent via marker # [FIX_UNIV_PORTFOLIO_RETURNS_V1]
"""
import re, shutil, datetime
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
MARK = "# [FIX_UNIV_PORTFOLIO_RETURNS_V1]"

NEW_FUNC = '''def _existing_portfolio_returns(conn: sqlite3.Connection, window_days: int = 90) -> pd.DataFrame:
    """Recupere les retours quotidiens des tickers en portefeuille pour calcul correlation.
    """ + MARK_INNER + """
    """
    cur = conn.execute(
        """
        SELECT i.ticker AS ticker, p.date AS date, p.close AS close
        FROM prices p
        JOIN instruments i ON i.id = p.instrument_id
        JOIN portfolio_targets t ON UPPER(t.ticker) = UPPER(i.ticker)
        WHERE t.active = 1
          AND p.date >= date('now', ?)
        ORDER BY i.ticker, p.date;
        """,
        (f'-{window_days + 30} day',),
    )
    rows = cur.fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot(index="date", columns="ticker", values="close").sort_index()
    rets = wide.pct_change().dropna(how="all")
    return rets.tail(window_days)
'''.replace('MARK_INNER + ""', f'"""{MARK}"""').replace('"""# [', '# [').replace(']"""', ']')

# Plus simple : on construit a la main pour eviter les pieges de string nesting
NEW_FUNC = (
    'def _existing_portfolio_returns(conn: sqlite3.Connection, window_days: int = 90) -> pd.DataFrame:\n'
    '    """Recupere les retours quotidiens des tickers en portefeuille pour calcul correlation."""\n'
    f'    {MARK}\n'
    '    cur = conn.execute(\n'
    '        """\n'
    '        SELECT i.ticker AS ticker, p.date AS date, p.close AS close\n'
    '        FROM prices p\n'
    '        JOIN instruments i ON i.id = p.instrument_id\n'
    '        JOIN portfolio_targets t ON UPPER(t.ticker) = UPPER(i.ticker)\n'
    '        WHERE t.active = 1\n'
    '          AND p.date >= date(\'now\', ?)\n'
    '        ORDER BY i.ticker, p.date;\n'
    '        """,\n'
    '        (f\'-{window_days + 30} day\',),\n'
    '    )\n'
    '    rows = cur.fetchall()\n'
    '    if not rows:\n'
    '        return pd.DataFrame()\n'
    '    df = pd.DataFrame(rows, columns=["ticker", "date", "close"])\n'
    '    df["date"] = pd.to_datetime(df["date"])\n'
    '    wide = df.pivot(index="date", columns="ticker", values="close").sort_index()\n'
    '    rets = wide.pct_change().dropna(how="all")\n'
    '    return rets.tail(window_days)\n'
)


def main():
    raw = AGENT.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    if MARK in txt:
        print(f"[SKIP] {MARK} deja present")
        return

    # Trouve la fonction par sa signature + corps jusqu'a la prochaine 'def ' top-level ou ligne vide suivie de def
    sig_re = re.compile(
        r'^def\s+_existing_portfolio_returns\s*\([^)]*\)\s*->\s*pd\.DataFrame:\s*\n',
        re.MULTILINE
    )
    m = sig_re.search(txt)
    if not m:
        print("[ERR] signature _existing_portfolio_returns introuvable"); return

    start = m.start()
    # cherche le prochain "^def " ou fin de fichier
    next_def = re.search(r'^def\s+\w+\s*\(', txt[m.end():], re.MULTILINE)
    if next_def:
        end = m.end() + next_def.start()
    else:
        end = len(txt)

    # remonte pour exclure les lignes vides juste avant la prochaine def
    while end > start and txt[end-1] in (' ', '\t'):
        end -= 1

    old = txt[start:end]
    print(f"[OK] fonction trouvee : lignes {txt[:start].count(chr(10))+1}..{txt[:end].count(chr(10))+1}")
    print(f"  Longueur : {len(old)} chars")
    print("--- old (premieres 200 chars) ---")
    print(old[:200])
    print("---")

    # Backup
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = AGENT.with_suffix(f".py.bak-{ts}-fix-portfolio-returns")
    shutil.copy2(AGENT, bak)
    print(f"[BACKUP] {bak.name}")

    # Replace : on garde 1 ligne vide entre fonctions
    new_txt = txt[:start] + NEW_FUNC + '\n\n' + txt[end:].lstrip('\n')

    # Verifs
    if 'p.ticker' in NEW_FUNC:
        print("[ERR] nouvelle requete contient encore p.ticker"); return
    if MARK not in new_txt:
        print("[ERR] marker non insere"); return
    # Verifie compte de def globalement (doit etre identique ou superieur)
    old_defs = txt.count('\ndef ')
    new_defs = new_txt.count('\ndef ')
    if new_defs < old_defs:
        print(f"[ERR] perte de def : {old_defs} -> {new_defs}"); return

    AGENT.write_bytes(new_txt.encode('utf-8'))
    print(f"[OK] {AGENT.name} ecrit ({len(txt)} -> {len(new_txt)} chars)")
    print()
    print("=" * 60)
    print("PROCHAINE ETAPE :")
    print("  1) Redemarre le serveur (api_server)")
    print("  2) Recharge la page, clique 'Lancer scan'")
    print("=" * 60)

if __name__ == "__main__":
    main()
