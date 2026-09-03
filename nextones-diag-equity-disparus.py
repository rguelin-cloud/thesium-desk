# -*- coding: utf-8 -*-
# [DIAG_EQUITY_DISPARUS_V1]
# Les equity (CAT, CSCO, TXN, AMD, PLD) etaient pending il y a ~1h
# puis ont disparu apres un nouveau scan.
# Ce script verifie :
#  1. Etat actuel universe_candidates (tous statuts) - cherche CAT/CSCO/TXN/AMD/PLD
#  2. Liste tous les scan_batch des dernieres 24h
#  3. Bloc EQUITY dans universe_expansion_agent.py (anti-dup, INSERT, conditions)
#  4. Trigger / contrainte UNIQUE sur (ticker) qui pourrait causer superseded
import os
import re
import sqlite3
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
AGENT = os.path.join(ROOT, "universe_expansion_agent.py")

EQUITY_WL = [
    "CAT","CSCO","TXN","AMD","PLD","AVGO","QCOM","ORCL","CRM","ADBE",
    "INTU","NOW","PLTR","ARM","NFLX","DIS","TMUS","CMCSA","HD","MCD",
    "NKE","SBUX","BKNG","LOW","COST","WMT","PG","KO","PEP","V","MA",
    "WFC","GS","MS","AXP","BRK-B","LLY","ABBV","MRK","PFE","TMO",
    "ISRG","BA","GE","RTX","HON","UNP","CVX","COP","LIN","NEE","SO",
]


def header(t):
    print()
    print("=" * 72)
    print("  " + t)
    print("=" * 72)


def step1_etat_db():
    header("1. universe_candidates - recherche des 5 equity disparus")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    target = ["CAT", "CSCO", "TXN", "AMD", "PLD"]
    for t in target:
        rows = cur.execute(
            "SELECT id, ticker, asset_class, status, score, scan_batch, proposed_at "
            "FROM universe_candidates WHERE ticker=? "
            "ORDER BY proposed_at DESC",
            (t,),
        ).fetchall()
        if not rows:
            print("  {} : AUCUNE trace en base".format(t))
        for r in rows:
            print(
                "  {} id={} class={} status={} score={} batch={} t={}".format(
                    r[1], r[0], r[2], r[3], r[4], r[5], r[6]
                )
            )

    print()
    print("  Tous equity (toutes statuts) :")
    rows = cur.execute(
        "SELECT ticker, status, COUNT(*) FROM universe_candidates "
        "WHERE asset_class='equity' GROUP BY ticker, status "
        "ORDER BY ticker, status"
    ).fetchall()
    if not rows:
        print("    (aucun)")
    for t, s, n in rows:
        print("    {:8s} {:12s} n={}".format(t, s, n))
    con.close()


def step2_scan_batches():
    header("2. Tous les scan_batch (24 dernieres heures)")
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT scan_batch, asset_class, COUNT(*), MIN(proposed_at), MAX(proposed_at) "
        "FROM universe_candidates "
        "WHERE proposed_at >= datetime('now', '-24 hours') "
        "GROUP BY scan_batch, asset_class "
        "ORDER BY MIN(proposed_at) DESC, asset_class"
    ).fetchall()
    last_batch = None
    for sb, ac, n, t0, t1 in rows:
        if sb != last_batch:
            print()
            print("  Batch {} :".format(sb))
            last_batch = sb
        print("    {:10s} n={} de {} a {}".format(ac, n, t0, t1))
    con.close()


def step3_bloc_equity():
    header("3. Bloc EQUITY dans universe_expansion_agent.py")
    if not os.path.isfile(AGENT):
        print("  [KO] fichier absent")
        return
    with open(AGENT, "r", encoding="utf-8-sig") as f:
        src = f.read()

    # Trouve la boucle for eq in EQUITY_WATCHLIST_V1
    m = re.search(
        r"(for\s+eq\s+in\s+EQUITY_WATCHLIST_V1[^\n]*\n(?:[ \t][^\n]*\n)+)",
        src,
    )
    if not m:
        print("  [KO] boucle EQUITY introuvable")
        return
    bloc = m.group(1)
    print("  Boucle EQUITY trouvee, {} lignes :".format(bloc.count("\n")))
    print("  -" * 35)
    for i, ln in enumerate(bloc.split("\n"), 1):
        print("  {:3d}: {}".format(i, ln[:130]))
    print("  -" * 35)


def step4_universe_schema():
    header("4. Schema universe_candidates + indexes")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    print("  PRAGMA table_info :")
    for r in cur.execute("PRAGMA table_info(universe_candidates)").fetchall():
        print("    cid={} name={} type={} notnull={} dflt={} pk={}".format(*r))
    print()
    print("  Indexes :")
    for r in cur.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='index' AND tbl_name='universe_candidates'"
    ).fetchall():
        print("    {} -> {}".format(r[0], r[1]))
    print()
    print("  Triggers :")
    for r in cur.execute(
        "SELECT name, sql FROM sqlite_master "
        "WHERE type='trigger' AND tbl_name='universe_candidates'"
    ).fetchall():
        print("    {} -> {}".format(r[0], r[1]))
    con.close()


def step5_filtres_potentiels():
    header("5. Verification filtres dans le bloc EQUITY")
    with open(AGENT, "r", encoding="utf-8-sig") as f:
        src = f.read()
    # Cherche : already_exists / IN universe_candidates / status='pending'
    patterns = [
        ("already exists", r"already.*exist"),
        ("existing tickers", r"existing[_ ]ticker"),
        ("anti-dup query", r"SELECT.*FROM\s+universe_candidates"),
        ("status='pending'", r"status\s*=\s*['\"]pending['\"]"),
        ("instruments check", r"FROM\s+instruments"),
        ("continue / skip", r"\bcontinue\b"),
        ("fetch_etf_history", r"fetch_etf_history"),
        ("yfinance", r"yfinance"),
    ]
    # Localiser la zone EQUITY
    m = re.search(
        r"for\s+eq\s+in\s+EQUITY_WATCHLIST_V1.*?(?=\n\S|\Z)",
        src,
        flags=re.DOTALL,
    )
    if not m:
        print("  [KO] zone EQUITY introuvable")
        return
    zone = m.group(0)
    print("  Taille zone EQUITY = {} chars".format(len(zone)))
    for label, pat in patterns:
        matches = re.findall(pat, zone, flags=re.IGNORECASE)
        print("  {:20s} : {} occurrence(s)".format(label, len(matches)))


def main():
    print("NEXTONES diag equity disparus")
    print("Python:", sys.version.split()[0])
    step1_etat_db()
    step2_scan_batches()
    step3_bloc_equity()
    step4_universe_schema()
    step5_filtres_potentiels()
    print()
    print("[FIN] colle la sortie complete")


if __name__ == "__main__":
    main()
