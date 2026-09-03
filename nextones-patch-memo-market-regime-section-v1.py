# -*- coding: utf-8 -*-
"""
Phase 2-ter : ajoute une section "Regime de Marche" au memo IC.

Modifications de memo_generator.py :
  1. Nouveau helper _build_market_regime_section(conn) (calque sur _build_risk_v2_section)
     - Lit le dernier cycle de regime_log + market_regime_log
     - Affiche : portfolio regime + equity regime + crypto regime
     - Detaille : VIX, vol annualisee, drawdown, multiplicateurs BUY/SELL
     - Indique l'impact pratique (take profit / acheter la baisse / neutre)
  2. Appel injecte dans la liste sections de generate_ic_memo,
     juste apres _build_risk_v2_section(conn)

Marker idempotent : [PATCH_MEMO_MARKET_REGIME_V1]
"""
import ast
import os
import py_compile
import re
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG = os.path.join(ROOT, "memo_generator.py")
MARKER = "[PATCH_MEMO_MARKET_REGIME_V1]"

# Lecture utf-8-sig
with open(MG, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print(f"[SKIP] Marker {MARKER} deja present.")
    sys.exit(0)

lines = src.splitlines(keepends=True)

# ----------------------------------------------------------------------
# Localisation des points d'injection
# ----------------------------------------------------------------------
# 1) Point d'injection du nouveau helper : juste avant 'if __name__ == "__main__":'
idx_main = None
for i, line in enumerate(lines):
    if re.match(r"if\s+__name__\s*==\s*[\"']__main__[\"']\s*:", line):
        idx_main = i
        break
if idx_main is None:
    print("[ERR] Bloc if __name__ == __main__ introuvable")
    sys.exit(1)

# 2) Point d'injection de l'appel : ligne contenant '_build_risk_v2_section(conn)'
idx_call = None
for i, line in enumerate(lines):
    if "_build_risk_v2_section(conn)" in line and "def " not in line:
        idx_call = i
        break
if idx_call is None:
    print("[ERR] Appel _build_risk_v2_section(conn) dans sections [] introuvable")
    sys.exit(2)

print(f"[OK] Injection helper a L{idx_main+1} (avant if __name__)")
print(f"[OK] Injection appel  a L{idx_call+1} (apres _build_risk_v2_section)")

# ----------------------------------------------------------------------
# Nouveau helper : 100% ASCII
# ----------------------------------------------------------------------
# Le marker est en commentaire Python. Tout le code injecte est ASCII pur.
# Pour les chaines markdown qui contiennent des accents : ils sont en escape
# unicode \uXXXX afin de garder le fichier source ASCII.
helper_code = (
    "\n\n"
    "# " + MARKER + "  ----------------------------------------------------------------\n"
    "def _build_market_regime_section(conn) -> str:\n"
    "    \"\"\"Section memo IC : regime de marche (equity vs crypto).\n\n"
    "    Lit la derniere ligne de regime_log + 2 lignes de market_regime_log.\n"
    "    Fallback gracieux si table absente ou pas de donnees.\n"
    "    \"\"\"\n"
    "    try:\n"
    "        import json as _json\n"
    "        # Dernier cycle\n"
    "        row = conn.execute(\n"
    "            \"SELECT cycle_id, regime, invested_pct, nav, equity_regime, \"\n"
    "            \"crypto_regime, equity_buy_mult, equity_sell_mult, \"\n"
    "            \"crypto_buy_mult, crypto_sell_mult, created_at \"\n"
    "            \"FROM regime_log ORDER BY id DESC LIMIT 1\"\n"
    "        ).fetchone()\n"
    "        if not row:\n"
    "            return \"## R\\u00e9gime de March\\u00e9\\n\\n*Aucun cycle disponible.*\\n\\n\"\n"
    "        # Detail equity / crypto depuis market_regime_log\n"
    "        cid = row[\"cycle_id\"] if hasattr(row, \"keys\") else row[0]\n"
    "        market_rows = conn.execute(\n"
    "            \"SELECT asset_class, regime, vix_value, realized_vol_pct, \"\n"
    "            \"drawdown_5d_pct, buy_mult, sell_mult, convergence_thresh, \"\n"
    "            \"details_json FROM market_regime_log WHERE cycle_id = ? \"\n"
    "            \"ORDER BY asset_class\",\n"
    "            (cid,)\n"
    "        ).fetchall()\n"
    "        # Helpers\n"
    "        def _impact(asset_class, regime):\n"
    "            if regime == \"STRESS\":\n"
    "                if asset_class == \"crypto\":\n"
    "                    return \"DCA crypto autoris\\u00e9 (BUY x1.8), SELL frein\\u00e9s (x0.5)\"\n"
    "                return \"Acheter la baisse equity (BUY x1.8), SELL frein\\u00e9s (x0.5)\"\n"
    "            if regime == \"CALM\":\n"
    "                if asset_class == \"crypto\":\n"
    "                    return \"Take profit crypto facilit\\u00e9 (SELL x1.5), BUY prudents (x0.7)\"\n"
    "                return \"Take profit equity facilit\\u00e9 (SELL x1.5), BUY prudents (x0.7)\"\n"
    "            return \"R\\u00e9gime neutre - aucune amplification\"\n"
    "        out = [\"## R\\u00e9gime de March\\u00e9 [MARKET_REGIME_V1]\\n\"]\n"
    "        out.append(\n"
    "            f\"**Cycle :** {cid}  -  **Portfolio regime :** {row['regime']} \"\n"
    "            f\"(invested={row['invested_pct']:.1f}%, NAV={row['nav']:,.0f} $)\\n\"\n"
    "        )\n"
    "        if not market_rows:\n"
    "            out.append(\"\\n*Aucune donn\\u00e9e market_regime_log pour ce cycle.*\\n\\n\")\n"
    "            return \"\\n\".join(out)\n"
    "        out.append(\"\")\n"
    "        out.append(\"| Asset class | R\\u00e9gime | VIX | Vol ann. | DD 5j | BUY mult | SELL mult | Impact pratique |\")\n"
    "        out.append(\"|---|---|---|---|---|---|---|---|\")\n"
    "        for r in market_rows:\n"
    "            ac = r[\"asset_class\"]\n"
    "            rg = r[\"regime\"]\n"
    "            vix = r[\"vix_value\"]\n"
    "            vol = r[\"realized_vol_pct\"]\n"
    "            dd = r[\"drawdown_5d_pct\"]\n"
    "            bm = r[\"buy_mult\"]\n"
    "            sm = r[\"sell_mult\"]\n"
    "            vix_str = f\"{vix:.2f}\" if vix is not None else \"-\"\n"
    "            vol_str = f\"{vol:.1f}%\" if vol is not None else \"-\"\n"
    "            dd_str = f\"{dd:.2f}%\" if dd is not None else \"-\"\n"
    "            bm_str = f\"x{bm:.2f}\" if bm is not None else \"-\"\n"
    "            sm_str = f\"x{sm:.2f}\" if sm is not None else \"-\"\n"
    "            impact = _impact(ac, rg)\n"
    "            out.append(\n"
    "                f\"| {ac} | **{rg}** | {vix_str} | {vol_str} | {dd_str} | \"\n"
    "                f\"{bm_str} | {sm_str} | {impact} |\"\n"
    "            )\n"
    "        # Detail des signaux (JSON dans details_json)\n"
    "        out.append(\"\")\n"
    "        out.append(\"### D\\u00e9tail des signaux\\n\")\n"
    "        for r in market_rows:\n"
    "            ac = r[\"asset_class\"]\n"
    "            try:\n"
    "                det = _json.loads(r[\"details_json\"] or \"{}\")\n"
    "            except Exception:\n"
    "                det = {}\n"
    "            calm_n = det.get(\"signals_calm\", \"-\")\n"
    "            stress_n = det.get(\"signals_stress\", \"-\")\n"
    "            sub = []\n"
    "            for k in (\"vix_signal\", \"vol_signal\", \"dd_signal\"):\n"
    "                if k in det:\n"
    "                    sub.append(f\"{k.replace('_signal','')}={det[k]}\")\n"
    "            sub_str = \", \".join(sub) if sub else \"-\"\n"
    "            out.append(\n"
    "                f\"- **{ac}** : {sub_str} -> {calm_n} CALM, {stress_n} STRESS \"\n"
    "                f\"-> classification **{r['regime']}**\"\n"
    "            )\n"
    "        out.append(\"\")\n"
    "        # Note methodologique courte\n"
    "        out.append(\n"
    "            \"_Equity : majorit\\u00e9 simple sur 3 signaux (VIX, vol 20j, drawdown 5j). \"\n"
    "            \"Crypto : 1 seul signal STRESS suffit (plus r\\u00e9actif). \"\n"
    "            \"Multiplicateurs : CALM 0.7/1.5, NORMAL 1.0/1.0, STRESS 1.8/0.5._\"\n"
    "        )\n"
    "        return \"\\n\".join(out) + \"\\n\\n\"\n"
    "    except Exception as _e_mr:\n"
    "        return f\"## R\\u00e9gime de March\\u00e9\\n\\n*Erreur lecture regime_log : {_e_mr}*\\n\\n\"\n"
    "# Fin " + MARKER + "  --------------------------------------------------------------\n"
    "\n"
)

# ----------------------------------------------------------------------
# Modification de generate_ic_memo : ajouter l'appel apres _build_risk_v2_section
# ----------------------------------------------------------------------
# Avant : "        _build_risk_v2_section(conn),  # [RISK_V2_WIRED]"
# Apres : ajouter la ligne "_build_market_regime_section(conn),  # [PATCH_MEMO_MARKET_REGIME_V1]"
old_call = lines[idx_call]
indent_call = old_call[: len(old_call) - len(old_call.lstrip())]
new_call = (
    old_call
    + indent_call + "_build_market_regime_section(conn),  # " + MARKER + "\n"
)

# Verification ASCII strict du code helper inject (le marker contient des [ et _ qui sont ASCII)
def _check_ascii(snippet, label):
    for i, ch in enumerate(snippet):
        if ord(ch) > 127:
            print(f"[ERR] Non-ASCII char dans {label} at pos {i}: U+{ord(ch):04X} ({ch!r})")
            sys.exit(20)
_check_ascii(helper_code, "helper_code")
_check_ascii(new_call, "new_call")

# ----------------------------------------------------------------------
# Application : modifier idx_call PUIS injecter helper avant idx_main
# (modifications dans new_lines, on fait l'ordre du bas vers le haut pour les indices)
# ----------------------------------------------------------------------
new_lines = list(lines)

# (A) Injection du helper avant idx_main
new_lines[idx_main] = helper_code + lines[idx_main]

# (B) Remplacement de la ligne d'appel
new_lines[idx_call] = new_call

new_src = "".join(new_lines)

# ----------------------------------------------------------------------
# Validation AST
# ----------------------------------------------------------------------
try:
    ast.parse(new_src)
    print("[OK] ast.parse passed")
except SyntaxError as e:
    print(f"[ERR] SyntaxError: {e}")
    err = new_src.splitlines()
    a = max(0, (e.lineno or 1) - 5)
    b = min(len(err), (e.lineno or 1) + 5)
    for k in range(a, b):
        print(f"  L{k+1:5} | {err[k][:170]}")
    sys.exit(10)

# ----------------------------------------------------------------------
# Backup + ecriture + py_compile
# ----------------------------------------------------------------------
ts = time.strftime("%Y%m%d-%H%M%S")
backup = MG + f".bak.{ts}"
shutil.copyfile(MG, backup)
print(f"[OK] Backup -> {backup}")

with open(MG, "w", encoding="utf-8", newline="") as f:
    f.write(new_src)
print(f"[OK] {MG} reecrit ({new_src.count(chr(10))} lignes)")

try:
    py_compile.compile(MG, doraise=True)
    print("[OK] py_compile passed")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile failed: {e}")
    shutil.copyfile(backup, MG)
    print(f"[ROLLBACK] depuis {backup}")
    sys.exit(11)

# Verifs
with open(MG, "r", encoding="utf-8-sig") as f:
    final = f.read()
n_marker = final.count(MARKER)
print(f"[OK] Marker {MARKER} present x{n_marker}")
print(f"[OK] Helper _build_market_regime_section x{final.count('def _build_market_regime_section')}")
print(f"[OK] Appel _build_market_regime_section(conn) x{final.count('_build_market_regime_section(conn)')}")

print()
print("=" * 70)
print("PATCH PHASE 2-ter APPLIQUE")
print("=" * 70)
print("Memo IC contient maintenant une section :")
print("  ## R\\u00e9gime de March\\u00e9 [MARKET_REGIME_V1]")
print()
print("Elle affiche :")
print("  - Cycle + portfolio regime + NAV")
print("  - Table equity/crypto : regime, VIX, vol, drawdown, mults BUY/SELL, impact pratique")
print("  - Detail des signaux (VIX/vol/dd) avec compteurs CALM/STRESS")
print("  - Note methodologique")
print()
print("Prochaine etape : regenerer le memo du dernier cycle pour visualiser")
