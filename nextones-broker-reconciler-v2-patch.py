# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-RECONCILER-V2-PATCH]
# Patche nextones-broker-reconciler.py (V1) en V2 :
#   - Ajoute fonction resolve_via_resolver(thesium_ticker) qui importe
#     nextones-broker-resolver.py et appelle resolve()
#   - Etend fetch_mappings() pour, en plus de instrument_broker_mapping (vide),
#     pre-resoudre les tickers via le resolver heuristique, qui est la source
#     reelle utilisee par le reste de la chaine (shadow exec, risk_broker_check).
#   - Idempotent : detecte le marker V2 et skip
#   - Validation : ast.parse + py_compile + import via subprocess avant ecriture
#
# Bonus : ajoute NVDA.US, TSLA.US, GOOGL.US a broker_universe_activtrades
# (absents du seed_v1, omission ; ActivTrades les propose normalement).
#
# Usage :
#   py -3.13 nextones-broker-reconciler-v2-patch.py
#   py -3.13 nextones-broker-reconciler-v2-patch.py --dry-run
#   py -3.13 nextones-broker-reconciler-v2-patch.py --skip-universe

import argparse
import ast
import os
import py_compile
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "nextones-broker-reconciler.py")
DB = os.path.join(PROD, "thesium.db")

V2_MARKER = "[NEXTONES-BROKER-RECONCILER-V2]"
V1_MARKER = "[NEXTONES-BROKER-RECONCILER-V1]"

# Tickers a ajouter a broker_universe_activtrades (omission du seed)
MISSING_UNIVERSE = [
    ("NVDA.US", "NVIDIA Corporation", "equity_us", "NVDA"),
    ("TSLA.US", "Tesla Inc", "equity_us", "TSLA"),
    ("GOOGL.US", "Alphabet Class A", "equity_us", "GOOGL"),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


# ---- helpers patch ------------------------------------------------
def already_patched(src):
    return V2_MARKER in src


def patch_marker(src):
    """Remplace marker V1 par V2 (en commentaire)."""
    if V1_MARKER in src:
        return src.replace(V1_MARKER, V2_MARKER)
    # sinon ajoute en haut
    return f"# {V2_MARKER}\n" + src


def patch_add_resolver_helper(src):
    """Ajoute la fonction resolve_via_resolver() apres open_db()."""
    helper = '''
# [NEXTONES-BROKER-RECONCILER-V2] helper resolver
_RESOLVER_MOD = None


def _load_resolver():
    """Charge nextones-broker-resolver.py par chemin (- dans le nom)."""
    global _RESOLVER_MOD
    if _RESOLVER_MOD is not None:
        return _RESOLVER_MOD
    import importlib.util as _ilu
    here = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, "nextones-broker-resolver.py")
    if not os.path.exists(p):
        print("[WARN] nextones-broker-resolver.py introuvable : " + p)
        return None
    spec = _ilu.spec_from_file_location("_nx_resolver", p)
    mod = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        _RESOLVER_MOD = mod
        return mod
    except Exception as e:
        print(f"[WARN] resolver import KO : {e}")
        return None


def resolve_via_resolver(thesium_ticker, con=None):
    """Retourne dict { broker_symbol, contract_size, lot_step, source }
    ou None si non resolvable."""
    mod = _load_resolver()
    if mod is None:
        return None
    fn = getattr(mod, "resolve", None)
    if fn is None:
        return None
    try:
        # signatures possibles : resolve(ticker, conn=...) ou resolve(ticker)
        try:
            res = fn(thesium_ticker, conn=con) if con else fn(thesium_ticker)
        except TypeError:
            res = fn(thesium_ticker)
    except Exception as e:
        print(f"[WARN] resolver({thesium_ticker}) exc : {e}")
        return None
    if res is None:
        return None
    # res est attendu sous forme dict avec broker_symbol/specs ou un tuple
    if isinstance(res, dict):
        bs = res.get("broker_symbol")
        if not bs:
            return None
        specs = res.get("specs") or res.get("diagnostics", {}).get("specs") or {}
        return {
            "broker_symbol": bs,
            "contract_size": float(specs.get("contract_size", 1.0)),
            "lot_step": float(specs.get("lot_step", 0.01)),
            "source": res.get("source") or res.get("resolver_source") or "resolver",
            "asset_class": res.get("asset_class")
            or res.get("diagnostics", {}).get("asset_class"),
        }
    return None


# [/NEXTONES-BROKER-RECONCILER-V2] helper resolver
'''
    if "_load_resolver" in src:
        return src  # idempotent
    # insertion apres la fonction open_db()
    needle = "def open_db():"
    idx = src.find(needle)
    if idx < 0:
        # fallback : avant fetch_thesium_positions
        needle = "def fetch_thesium_positions("
        idx = src.find(needle)
        if idx < 0:
            print("[WARN] impossible de trouver point d'insertion")
            return src
        return src[:idx] + helper + "\n\n" + src[idx:]
    # avancer apres la fin de open_db (jusqu'au prochain def ou ligne vide)
    end = src.find("\ndef ", idx + len(needle))
    if end < 0:
        end = len(src)
    return src[:end] + "\n" + helper + src[end:]


def patch_fetch_mappings(src):
    """Etend fetch_mappings : si la table est vide, complete avec le resolver
    sur la liste des thesium_tickers fournie."""
    new_sig = "def fetch_mappings(con, thesium_tickers=None):"
    old_sig = "def fetch_mappings(con):"
    if "thesium_tickers=None" in src:
        return src  # idempotent
    if old_sig not in src:
        print("[WARN] signature fetch_mappings(con) introuvable")
        return src
    src2 = src.replace(old_sig, new_sig)
    # ajoute le complement resolver avant le return
    completion = '''
    # [NEXTONES-BROKER-RECONCILER-V2] completion via resolver
    if thesium_tickers:
        for t in thesium_tickers:
            if t in by_thesium:
                continue
            r = resolve_via_resolver(t, con)
            if r is None:
                continue
            d = {
                "thesium_ticker": t,
                "broker_symbol": r["broker_symbol"],
                "contract_size": r["contract_size"],
                "lot_step": r["lot_step"],
            }
            by_broker[r["broker_symbol"]] = d
            by_thesium[t] = d
    # [/NEXTONES-BROKER-RECONCILER-V2]
'''
    needle_ret = "    return by_broker, by_thesium"
    if needle_ret not in src2:
        print("[WARN] return by_broker,by_thesium introuvable")
        return src2
    src2 = src2.replace(needle_ret, completion + needle_ret, 1)
    return src2


def patch_main_call(src):
    """Appelle fetch_mappings avec la liste des tickers thesium."""
    # cherche : mapping_by_broker, mapping_by_thesium = fetch_mappings(con)
    old = "fetch_mappings(con)"
    new = (
        "fetch_mappings(con, "
        "thesium_tickers=[p['thesium_ticker'] for p in thesium_positions])"
    )
    if "thesium_tickers=" in src:
        return src
    if old not in src:
        print("[WARN] appel fetch_mappings(con) introuvable")
        return src
    return src.replace(old, new, 1)


# ---- universe seed bonus ------------------------------------------
def add_missing_to_universe(verbose=False):
    if not os.path.exists(DB):
        print("[WARN] db introuvable :", DB)
        return
    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("PRAGMA busy_timeout=10000")
    cur = con.cursor()
    ts = now_iso()
    inserted = 0
    for (sym, desc, ac, und) in MISSING_UNIVERSE:
        r = cur.execute(
            "SELECT 1 FROM broker_universe_activtrades WHERE broker_symbol=?",
            (sym,)
        ).fetchone()
        if r is not None:
            if verbose:
                print(f"  [skip] {sym} deja present")
            continue
        cur.execute(
            "INSERT INTO broker_universe_activtrades "
            "(broker_symbol, description, asset_class, underlying_ticker, "
            " is_cfd, quote_ccy, discovered_at, last_seen_at, notes) "
            "VALUES (?, ?, ?, ?, 1, 'USD', ?, ?, "
            "'manual_seed_v2_2026-05-30')",
            (sym, desc, ac, und, ts, ts),
        )
        inserted += 1
        print(f"  [+] {sym} ajoute (asset_class={ac}, underlying={und})")
    con.commit()
    con.close()
    print(f"  total ajoutes : {inserted} / {len(MISSING_UNIVERSE)}")


# ---- pipeline -----------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="affiche le diff sans ecrire")
    ap.add_argument("--skip-universe", action="store_true",
                    help="n'ajoute pas NVDA/TSLA/GOOGL a l'univers")
    args = ap.parse_args()

    if not os.path.exists(TARGET):
        print("[FAIL] target introuvable :", TARGET)
        sys.exit(2)

    banner("[1] Lecture nextones-broker-reconciler.py")
    with open(TARGET, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    print(f"  taille initiale : {len(src)} octets")

    if already_patched(src):
        print(f"  [OK] V2 marker deja present : {V2_MARKER}")
        print("  rien a faire pour le patch python")
    else:
        banner("[2] Application des patches V2")
        src2 = src
        src2 = patch_marker(src2)
        src2 = patch_add_resolver_helper(src2)
        src2 = patch_fetch_mappings(src2)
        src2 = patch_main_call(src2)
        print(f"  taille apres patch : {len(src2)} octets")

        banner("[3] Validation ast.parse + py_compile")
        try:
            ast.parse(src2)
        except SyntaxError as e:
            print(f"[FAIL] ast.parse : {e}")
            sys.exit(1)
        # ecrit temp pour py_compile
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(src2)
            tmpname = tf.name
        try:
            py_compile.compile(tmpname, doraise=True)
            print("  [OK] py_compile")
        except py_compile.PyCompileError as e:
            print(f"[FAIL] py_compile : {e}")
            sys.exit(1)
        finally:
            try:
                os.unlink(tmpname)
            except Exception:
                pass

        banner("[4] Smoke import via subprocess")
        # ecrit temporairement dans target.tmp pour import test
        tmp_target = TARGET + ".tmpv2"
        with open(tmp_target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src2)
        try:
            # import via subprocess (sans executer main, juste --help)
            r = subprocess.run(
                ["py", "-3.13", tmp_target, "--help"],
                capture_output=True, text=True, timeout=30,
                cwd=PROD,
            )
            if r.returncode != 0:
                print(f"[FAIL] smoke --help rc={r.returncode}")
                print("STDOUT:", r.stdout[-500:])
                print("STDERR:", r.stderr[-500:])
                sys.exit(1)
            print("  [OK] smoke --help rc=0")
        finally:
            try:
                os.unlink(tmp_target)
            except Exception:
                pass

        if args.dry_run:
            banner("[5] DRY-RUN : pas d'ecriture")
        else:
            banner("[5] Backup + ecriture")
            bak = TARGET + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(TARGET, bak)
            print(f"  backup : {bak}")
            with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(src2)
            print(f"  ecrit  : {TARGET}")

    if args.skip_universe:
        banner("[6] --skip-universe : pas d'ajout NVDA/TSLA/GOOGL")
    else:
        banner("[6] Ajout NVDA.US / TSLA.US / GOOGL.US a l'univers")
        add_missing_to_universe(verbose=True)

    banner("[7] DONE")
    print("Prochaine etape :")
    print("  py -3.13 nextones-broker-reconciler.py --no-broker --verbose")


if __name__ == "__main__":
    main()
