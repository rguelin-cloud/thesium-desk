# -*- coding: utf-8 -*-
"""
[FIX_ETF_HISTORY_SQL_V1]
Corrige la requete SQL de fetch_etf_history : remplace
  SELECT date, close FROM prices WHERE ticker = ? ...
par
  SELECT p.date, p.close FROM prices p
  JOIN instruments i ON i.id = p.instrument_id
  WHERE UPPER(i.ticker) = UPPER(?) ...

Et ajoute un sleep entre appels CoinGecko dans fetch_crypto_history (rate-limit 429).
Idempotent via marker [FIX_ETF_SQL_V1].
"""
import re, shutil, datetime
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
MARK_SQL = "# [FIX_ETF_SQL_V1]"
MARK_SLEEP = "# [FIX_CG_SLEEP_V1]"

OLD_SQL = '"SELECT date, close FROM prices WHERE ticker = ? AND date >= date(\'now\', ?) ORDER BY date;"'
NEW_SQL = (
    '"""\n'
    '        SELECT p.date, p.close FROM prices p\n'
    '        JOIN instruments i ON i.id = p.instrument_id\n'
    '        WHERE UPPER(i.ticker) = UPPER(?) AND p.date >= date(\'now\', ?)\n'
    '        ORDER BY p.date;\n'
    '        """'
)

def main():
    raw = AGENT.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        txt = raw[3:].decode('utf-8', errors='replace')
    else:
        txt = raw.decode('utf-8', errors='replace')

    changed = False

    # 1) Fix SQL fetch_etf_history
    if MARK_SQL in txt:
        print(f"[SKIP SQL] {MARK_SQL} deja present")
    else:
        if OLD_SQL not in txt:
            print("[ERR] requete SQL ancienne introuvable")
            print(f"  Recherche: {OLD_SQL!r}")
            # Tente une recherche plus laxe
            m = re.search(r'"SELECT date, close FROM prices WHERE ticker[^"]+"', txt)
            if m:
                print(f"  Variante trouvee : {m.group(0)!r}")
            return
        txt = txt.replace(OLD_SQL, NEW_SQL + f' {MARK_SQL}', 1)
        print(f"[OK] SQL fetch_etf_history patche")
        changed = True

    # 2) Ajoute time.sleep dans fetch_crypto_history (apres r.raise_for_status())
    # Cherche la fonction et ajoute un sleep avant chaque appel CoinGecko
    if MARK_SLEEP in txt:
        print(f"[SKIP SLEEP] {MARK_SLEEP} deja present")
    else:
        # Strategie : ajouter un sleep(1.2) AVANT le requests.get dans fetch_crypto_history
        # On cible la signature fetch_crypto_history puis le premier requests.get
        m = re.search(
            r'(def\s+fetch_crypto_history[^:]+:\s*\n\s*"""[^"]+"""\s*\n)(\s*)try:',
            txt
        )
        if m:
            indent = m.group(2)
            insert = f'{indent}import time as _t; _t.sleep(1.5)  {MARK_SLEEP}\n{indent}try:'
            txt = txt[:m.start()] + m.group(1) + insert + txt[m.end():]
            print("[OK] sleep ajoute dans fetch_crypto_history")
            changed = True
        else:
            print("[WARN] signature fetch_crypto_history non trouvee pour sleep")

    if not changed:
        print("[INFO] rien a faire")
        return

    # Verifs
    if 'p.ticker' in txt:
        print("[WARN] p.ticker encore present dans le fichier — verifie manuellement")
        for m in re.finditer(r'p\.ticker', txt):
            line_no = txt[:m.start()].count('\n') + 1
            print(f"  L{line_no}: p.ticker")

    # Backup + ecriture
    ts = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    bak = AGENT.with_suffix(f".py.bak-{ts}-fix-etf-sql")
    shutil.copy2(AGENT, bak)
    print(f"[BACKUP] {bak.name}")

    AGENT.write_bytes(txt.encode('utf-8'))
    print(f"[OK] {AGENT.name} ecrit")
    print()
    print("=" * 60)
    print("Verifie en relancant le diag :")
    print("  py -3.13 .\\nextones-diag-scan-empty.py")
    print("=" * 60)

if __name__ == "__main__":
    main()
