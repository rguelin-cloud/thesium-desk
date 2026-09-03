"""
Fix groupe data_crypto.py :

Bug 1 : ETF_MAP contient 4 tickers (IBIT/ETHA/GSOL/GLNK) qui crashent en boucle
        via finvizfinance. Vider ETF_MAP -> fetch_crypto_signals() retourne []
        proprement, sig_map vide, tous les champs technicals => None.

Bug 2 : refresh_crypto_prices_to_db() contient 4 code-lignes buggees
        {{...}} au lieu de {...} (patch initial nextones-add-crypto-cg-scheduler-v1
        avait echappe accolades en pensant faire du templating).
        Lignes concernees : L193, L226-L231, L236, L238-L239

        DOCSTRING L186 : reste inchange, `{{updated,...}}` en docstring est OK.

Marker : # [DATA_CRYPTO_MULTIFIX_V1]
"""
import os
import shutil
import sys
import time
import re

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_crypto.py"
MARK = "# [DATA_CRYPTO_MULTIFIX_V1]"
TS = time.strftime("%Y%m%d_%H%M%S")

# Remplacements bloc par bloc, tous verbatim depuis les diags precedents

REPLACEMENTS = [
    # BUG 1 - ETF_MAP : vider (garder tickers en commentaire pour reference)
    (
        "ETF_MAP = {\n"
        "    'BTC':  'IBIT',   # iShares Bitcoin Trust\n"
        "    'ETH':  'ETHA',   # iShares Ethereum Trust\n"
        "    'SOL':  'GSOL',   # Grayscale Solana Trust\n"
        "    'LINK': 'GLNK',   # Grayscale Chainlink Trust\n"
        "}\n",

        "ETF_MAP = {}  " + MARK + "  disabled: finvizfinance crashe sur les 4 ETF spot crypto\n"
        "# ETF_MAP historique (a reactiver si finvizfinance supporte un jour ces tickers,\n"
        "# ou si on remplace par calcul RSI/SMA maison depuis la table 'prices') :\n"
        "#     'BTC':  'IBIT',   # iShares Bitcoin Trust\n"
        "#     'ETH':  'ETHA',   # iShares Ethereum Trust\n"
        "#     'SOL':  'GSOL',   # Grayscale Solana Trust\n"
        "#     'LINK': 'GLNK',   # Grayscale Chainlink Trust\n",
    ),

    # BUG 2.1 - L193 : result = {{...}}
    (
        "    result = {{\"updated\": [], \"skipped\": [], \"errors\": []}}\n",
        "    result = {\"updated\": [], \"skipped\": [], \"errors\": []}  " + MARK + "\n",
    ),

    # BUG 2.2 - L226 : ohlc_row = {{ ... L231 : }}
    (
        "            ohlc_row = {{\n",
        "            ohlc_row = {  " + MARK + "\n",
    ),
    (
        "            }}\n",
        "            }  " + MARK + "\n",
    ),

    # BUG 2.3 - L236 : result["errors"].append({{"ticker": ticker, "err": str(e)}})
    (
        '                result["errors"].append({{"ticker": ticker, "err": str(e)}})\n',
        '                result["errors"].append({"ticker": ticker, "err": str(e)})  ' + MARK + "\n",
    ),

    # BUG 2.4 - L238-239 : f-string print avec {{...}} au lieu de {...}
    (
        '        print(f"[crypto_cg] updated={{len(result[\'updated\'])}} "\n'
        '              f"skipped={{len(result[\'skipped\'])}} errors={{len(result[\'errors\'])}}")\n',

        '        print(f"[crypto_cg] updated={len(result[\'updated\'])} "  ' + MARK + "\n"
        '              f"skipped={len(result[\'skipped\'])} errors={len(result[\'errors\'])}")\n',
    ),
]


def main():
    if not os.path.exists(F):
        print("[ERR] file not found:", F)
        return 2

    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    if MARK in src:
        print("[SKIP] fix already applied (marker present)")
        return 0

    # Verifie que TOUS les OLD sont presents verbatim avant de faire quoi que ce soit
    print("[STAGE 1] Recherche verbatim des 6 blocs a remplacer")
    print("-" * 70)
    missing = []
    for idx, (old, new) in enumerate(REPLACEMENTS, 1):
        if old in src:
            # Certains OLD (ex "            }}\n") peuvent apparaitre plusieurs fois
            # -> on veut s'assurer que remplacement precis marchera
            n = src.count(old)
            print(f"  [OK] bloc #{idx}: {n} occurrence(s)")
        else:
            print(f"  [MISS] bloc #{idx}: NOT FOUND verbatim")
            print(f"         old = {old[:80]!r}...")
            missing.append(idx)

    if missing:
        print()
        print("[ABORT] blocs manquants:", missing)
        return 3

    # Stage 2 : appliquer les remplacements dans l'ordre
    print()
    print("[STAGE 2] Application des remplacements")
    print("-" * 70)

    new_src = src

    for idx, (old, new) in enumerate(REPLACEMENTS, 1):
        n_before = new_src.count(old)
        # Remplace UNIQUEMENT la premiere occurrence pour rester chirurgical
        new_src = new_src.replace(old, new, 1)
        n_after = new_src.count(old)
        applied = n_before - n_after
        print(f"  [#{idx}] applied={applied} (before={n_before} after={n_after})")

    if new_src == src:
        print("[ERR] no change produced")
        return 4

    # Validation syntaxique
    try:
        compile(new_src, F, "exec")
        print()
        print("[OK] compile() passes on patched source")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError post-patch: {e}")
        # Ecrit dans temp pour inspection
        tmp = F + ".broken." + TS
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_src)
        print(f"       broken source ecrit dans: {tmp}")
        return 5

    # Backup + write
    bak = F + ".bak." + TS
    shutil.copy2(F, bak)
    print("[BAK]", bak)

    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print("[OK] written:", F)

    # Sanity check final
    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        check = fh.read()

    print()
    print("[POST-WRITE CHECKS]")
    checks = [
        ("ETF_MAP = {}", "ETF_MAP vide"),
        ("result = {\"updated\": [], \"skipped\": [], \"errors\": []}", "L193 fix"),
        ('result["errors"].append({"ticker": ticker, "err": str(e)})', "L236 fix"),
        ('updated={len(result[\'updated\'])}', "L238 f-string fix"),
        (MARK, "marker present"),
    ]
    for needle, label in checks:
        n = check.count(needle)
        tag = "OK" if n > 0 else "MISSING"
        print(f"  [{tag}] {label}: {n} occurrences")

    # Anti-regression
    remaining_bad = check.count('{{"updated": [], "skipped": []')
    remaining_bad2 = check.count("updated={{len(")
    print(f"  [{'OK' if remaining_bad == 0 else 'STILL BUGGY'}] no '{{{{\"updated\"' left: {remaining_bad}")
    print(f"  [{'OK' if remaining_bad2 == 0 else 'STILL BUGGY'}] no 'updated={{{{len(' left: {remaining_bad2}")

    # Verifier que import + call ne crashent plus (runtime test)
    print()
    print("[STAGE 3] Runtime validation")
    try:
        # Force reload
        import importlib
        sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
        if "data_crypto" in sys.modules:
            importlib.reload(sys.modules["data_crypto"])
        else:
            import data_crypto  # noqa: F401
        print("  [OK] data_crypto (re)imported successfully")

        # Test fetch_crypto_signals (doit retourner [] proprement, sans crash)
        from data_crypto import fetch_crypto_signals
        sig = fetch_crypto_signals()
        print(f"  [OK] fetch_crypto_signals() -> {type(sig).__name__} len={len(sig)}")

    except Exception as e:
        print(f"  [WARN] runtime test failed: {type(e).__name__}: {e}")
        print("         (patch en fichier OK, mais reload interpreter conseille)")

    print()
    print("[NEXT] Restart uvicorn pour recharger data_crypto en memoire")
    print("[NEXT] Prochain refresh CG dans <=2h : doit ecrire les prix BTC/ETH/SOL/LINK")
    print("[NEXT] Verifier logs : plus de 'Finviz error for IBIT/ETHA/GSOL/GLNK'")
    print("[NEXT] /api/crypto/overview : rsi/sma20/etc en None pour crypto (mais prix OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
