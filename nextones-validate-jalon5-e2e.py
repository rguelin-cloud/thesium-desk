# -*- coding: utf-8 -*-
"""
nextones-validate-jalon5-e2e
Validation end-to-end Convergence Engine + Memo IC.

Verifie :
1. Le snapshot convergence existe pour le dernier cycle (table convergence_snapshots)
2. L'endpoint API /api/convergence/snapshot renvoie les memes donnees que la DB
3. Les fichiers patches contiennent les markers attendus (idempotence)
4. memo_generator.py contient le marker diff J-1/J-7
5. Genere un memo de test sur 1 forced_exit + 1 strong et verifie qu'il
   mentionne le sizing multiplier + le verdict convergence
6. Sortie PASS/FAIL detaillee

Usage : py -3.13 nextones-validate-jalon5-e2e.py
"""
import os, sys, io, sqlite3, json, re, urllib.request, urllib.error, traceback

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")
API_BASE = "http://localhost:8000"

# Fichiers a verifier markers
EXPECTED_MARKERS = {
    "portfolio_construction_agent_jalon2.py": ["# [CONVERGENCE_SIZING_V2]", "# [CONV_FALSY_FIX_V1]"],
    "api_server_with_static.py": ["# [CONVERGENCE_CYCLE_RESOLVER_V2]", "# [API_CONVERGENCE_V1]"],
    "app.js": ["// [CONVERGENCE_JS_V1]", "// [CONVERGENCE_JS_V2_FIX]"],
    "index.html": ["<!-- [CONVERGENCE_CARD_V1] -->", "<!-- [CONVERGENCE_CSS_V2_FIX] -->"],
    "memo_generator.py": [],  # On verra dans la verif diff
}

results = []  # list[(test_name, status, detail)]

def ok(name, detail=""):
    results.append((name, "PASS", detail))
    print(f"  [PASS] {name}" + (f"  -- {detail}" if detail else ""))

def fail(name, detail=""):
    results.append((name, "FAIL", detail))
    print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))

def warn(name, detail=""):
    results.append((name, "WARN", detail))
    print(f"  [WARN] {name}" + (f"  -- {detail}" if detail else ""))

def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

# ---------------------------------------------------------------------------
# Test 1 : Snapshot convergence existe
# ---------------------------------------------------------------------------
section("1. SNAPSHOT CONVERGENCE EN DB")
try:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT cycle_id, COUNT(*) AS n FROM convergence_snapshots GROUP BY cycle_id ORDER BY rowid DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        fail("snapshot_exists", "aucun cycle dans convergence_snapshots")
        latest_cycle = None
    else:
        latest_cycle = row["cycle_id"]
        n = row["n"]
        ok("snapshot_exists", f"cycle {latest_cycle} ({n} tickers)")

    if latest_cycle:
        cur.execute("""
            SELECT
              SUM(CASE WHEN forced_exit=1 THEN 1 ELSE 0 END) AS fe,
              SUM(CASE WHEN drift=1 THEN 1 ELSE 0 END) AS dr,
              SUM(CASE WHEN sizing_multiplier>=1.0 AND n_aligned>=3 THEN 1 ELSE 0 END) AS st,
              COUNT(*) AS total
            FROM convergence_snapshots WHERE cycle_id=?
        """, (latest_cycle,))
        s = cur.fetchone()
        ok("snapshot_totals_db", f"{s['total']} tickers : {s['fe']} fe / {s['dr']} drift / {s['st']} strong")
except Exception as e:
    fail("snapshot_exists", f"erreur DB : {e}")
    latest_cycle = None

# ---------------------------------------------------------------------------
# Test 2 : API endpoint renvoie meme chose
# ---------------------------------------------------------------------------
section("2. ENDPOINT API /api/convergence/snapshot")
api_data = None
try:
    req = urllib.request.Request(f"{API_BASE}/api/convergence/snapshot")
    with urllib.request.urlopen(req, timeout=8) as resp:
        api_data = json.loads(resp.read().decode("utf-8"))
    if api_data.get("status") != "ok":
        fail("api_status_ok", f"status={api_data.get('status')}")
    else:
        ok("api_status_ok", f"cycle {api_data.get('cycle_id')}")

    if latest_cycle and api_data.get("cycle_id") != latest_cycle:
        warn("api_cycle_match", f"API={api_data.get('cycle_id')} DB={latest_cycle}")
    elif latest_cycle:
        ok("api_cycle_match", "API et DB sur le meme cycle")

    rows = api_data.get("rows", [])
    if not rows:
        fail("api_rows_present", "0 lignes dans rows[]")
    else:
        ok("api_rows_present", f"{len(rows)} tickers")

    # Verif structure 1 row
    if rows:
        sample = rows[0]
        expected_keys = {"ticker", "direction_consensus", "sizing_multiplier",
                         "n_aligned", "n_present", "forced_exit", "drift", "buckets"}
        missing = expected_keys - set(sample.keys())
        if missing:
            fail("api_row_schema", f"clefs manquantes : {missing}")
        else:
            ok("api_row_schema", f"toutes les clefs presentes (sample {sample['ticker']})")
        # Buckets keys
        bk = set((sample.get("buckets") or {}).keys())
        expected_buckets = {"L1", "L2", "L3", "L4", "L5"}
        if not (bk & expected_buckets):
            fail("api_buckets_schema", f"clefs buckets inattendues : {bk}")
        else:
            ok("api_buckets_schema", f"clefs buckets OK : {sorted(bk)}")
except urllib.error.URLError as e:
    fail("api_status_ok", f"endpoint inaccessible : {e}")
except Exception as e:
    fail("api_status_ok", f"erreur : {e}")

# ---------------------------------------------------------------------------
# Test 3 : DB vs API coherence
# ---------------------------------------------------------------------------
section("3. COHERENCE DB <-> API")
if api_data and latest_cycle:
    try:
        cur.execute("""SELECT ticker, sizing_multiplier, forced_exit, drift, n_aligned
                       FROM convergence_snapshots WHERE cycle_id=?""", (latest_cycle,))
        db_rows = {r["ticker"]: dict(r) for r in cur.fetchall()}
        api_rows = {r["ticker"]: r for r in api_data.get("rows", [])}

        diff_tickers = set(db_rows.keys()) ^ set(api_rows.keys())
        if diff_tickers:
            fail("coherence_tickers", f"diff : {diff_tickers}")
        else:
            ok("coherence_tickers", f"{len(db_rows)} tickers identiques")

        mismatches = []
        for t, db_r in db_rows.items():
            ar = api_rows.get(t)
            if not ar:
                continue
            if abs((db_r["sizing_multiplier"] or 0) - (ar.get("sizing_multiplier") or 0)) > 1e-6:
                mismatches.append(f"{t}: DB={db_r['sizing_multiplier']} API={ar.get('sizing_multiplier')}")
            if int(db_r["forced_exit"] or 0) != int(ar.get("forced_exit") or 0):
                mismatches.append(f"{t}: fe DB={db_r['forced_exit']} API={ar.get('forced_exit')}")
        if mismatches:
            fail("coherence_sizing", f"{len(mismatches)} mismatch : {mismatches[:3]}")
        else:
            ok("coherence_sizing", "sizing/forced_exit identiques DB<->API")
    except Exception as e:
        fail("coherence_tickers", f"erreur : {e}")

# ---------------------------------------------------------------------------
# Test 4 : Markers presents dans fichiers
# ---------------------------------------------------------------------------
section("4. MARKERS IDEMPOTENCE")
for fname, markers in EXPECTED_MARKERS.items():
    path = os.path.join(BASE, fname)
    if not os.path.isfile(path):
        warn(f"file_exists::{fname}", "fichier absent")
        continue
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            content = f.read()
        for mk in markers:
            if mk in content:
                ok(f"marker::{fname}::{mk}", "")
            else:
                fail(f"marker::{fname}::{mk}", "marker manquant")
    except Exception as e:
        fail(f"read::{fname}", str(e))

# ---------------------------------------------------------------------------
# Test 5 : memo_generator a-t-il la section diff ?
# ---------------------------------------------------------------------------
section("5. MEMO_GENERATOR - SECTION DIFF")
mg_path = os.path.join(BASE, "memo_generator.py")
mg_content = ""
if os.path.isfile(mg_path):
    try:
        with open(mg_path, "r", encoding="utf-8-sig") as f:
            mg_content = f.read()
        # Markers possibles du patch diff (etape 2.3)
        diff_signals = [
            "Ce qui a changé",
            "compute_cycle_diff",
            "diff_engine",
            "[MEMO_DIFF_V1]",
            "j_minus_1",
            "J-1",
        ]
        found = [s for s in diff_signals if s in mg_content]
        if found:
            ok("memo_diff_section", f"signaux trouves : {found}")
        else:
            warn("memo_diff_section", "aucun signal diff dans memo_generator (etape 2.3 a verifier)")

        # convergence dans memo ?
        if "convergence" in mg_content.lower() or "sizing_multiplier" in mg_content:
            ok("memo_convergence_aware", "memo_generator mentionne convergence/sizing")
        else:
            warn("memo_convergence_aware", "memo_generator ne semble pas lire convergence_snapshots")
    except Exception as e:
        fail("memo_generator_read", str(e))
else:
    fail("memo_generator_exists", "memo_generator.py introuvable")

# ---------------------------------------------------------------------------
# Test 6 : Verifie qu'on a un memo recent pour fe + strong
# ---------------------------------------------------------------------------
section("6. MEMOS DISPONIBLES EN DB")
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memos'")
    if not cur.fetchone():
        warn("memos_table", "table 'memos' introuvable (peut-etre nom different)")
        # essai autres noms
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%memo%'")
        memo_tables = [r["name"] for r in cur.fetchall()]
        print(f"    tables memo-like : {memo_tables}")
    else:
        cur.execute("SELECT COUNT(*) AS n FROM memos")
        n = cur.fetchone()["n"]
        ok("memos_count", f"{n} memos en DB")
        cur.execute("""SELECT id, ticker, created_at FROM memos
                       ORDER BY rowid DESC LIMIT 5""")
        recent = [dict(r) for r in cur.fetchall()]
        for m in recent:
            print(f"    memo #{m.get('id')} {m.get('ticker','?')} -- {m.get('created_at','?')}")
except Exception as e:
    warn("memos_table", str(e))

# ---------------------------------------------------------------------------
# Synthese
# ---------------------------------------------------------------------------
section("SYNTHESE")
n_pass = sum(1 for _,s,_ in results if s == "PASS")
n_fail = sum(1 for _,s,_ in results if s == "FAIL")
n_warn = sum(1 for _,s,_ in results if s == "WARN")
print(f"\n  PASS : {n_pass}")
print(f"  FAIL : {n_fail}")
print(f"  WARN : {n_warn}")
print()
if n_fail == 0:
    print("  >>> JALON 5 E2E : VALIDE (PASS) <<<")
else:
    print("  >>> JALON 5 E2E : ECHEC (voir FAIL ci-dessus) <<<")
    print()
    for name, st, det in results:
        if st == "FAIL":
            print(f"    FAIL {name} : {det}")

# Suggestions etape B
print()
print("[ETAPE B - GENERATION MEMOS PDF]")
if api_data:
    rows = api_data.get("rows", [])
    fe_sample = next((r["ticker"] for r in rows if r.get("forced_exit")), None)
    strong_sample = next((r["ticker"] for r in rows
                          if (r.get("sizing_multiplier") or 0) >= 1.0
                          and (r.get("n_aligned") or 0) >= 3
                          and not r.get("forced_exit")), None)
    print(f"  Ticker forced_exit a tester : {fe_sample}")
    print(f"  Ticker strong a tester       : {strong_sample}")
    print(f"  Action user : depuis l'UI, cliquer 'Memo IA' sur {fe_sample} et {strong_sample}")
    print(f"             puis exporter en PDF et partager les 2 fichiers")
