# =====================================================================
# apply_crypto_patch_v3.ps1
# Jalon 3 - Patch complet : crypto + _fetch_log_returns + Sharpe reel
# Remplace v2 (ajout du helper manquant)
# =====================================================================

$ErrorActionPreference = "Stop"
$Root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
Set-Location $Root

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  JALON 3 - PATCH CRYPTO + R v3 (complet)" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host ""

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "$Root\_backups_crypto_v3_$ts"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item "$Root\execution_engine.py" "$backupDir\" -Force
Copy-Item "$Root\portfolio_construction_agent.py" "$backupDir\" -Force
Write-Host "[1/5] Backup OK : $backupDir" -ForegroundColor Green

$patchPy = @'
import re
import sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# =====================================================================
# A. execution_engine.py - patch crypto (ligne par ligne)
# =====================================================================
print()
print("=" * 60)
print("A. execution_engine.py - crypto qty fractionnaire")
print("=" * 60)

ee_path = ROOT / "execution_engine.py"
src = ee_path.read_text(encoding="utf-8", errors="ignore")

if "# Jalon 3 - qty fractionnaire crypto" in src:
    print("[A] Deja applique (skip)")
else:
    lines = src.splitlines(keepends=False)

    target_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\s+qty\s*=\s*math\.floor\(delta_val\s*/\s*price\)", line):
            if 1430 <= i + 1 <= 1470:
                target_idx = i
                break

    if target_idx is None:
        print("[A] Ligne cible introuvable - dump L1438-1460 :")
        for i in range(1438, 1460):
            if i < len(lines):
                print(f"    L{i+1}  {lines[i]}")
    else:
        print(f"[A] Ligne cible trouvee : L{target_idx+1}")
        m = re.match(r"^(\s+)", lines[target_idx])
        indent = m.group(1) if m else "        "

        new_block = [
            f"{indent}# Jalon 3 - qty fractionnaire crypto",
            f"{indent}CRYPTO_TICKERS = {{'BTC', 'ETH', 'LINK', 'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX'}}",
            f"{indent}is_crypto = ticker in CRYPTO_TICKERS",
            f"{indent}if is_crypto:",
            f"{indent}    qty = round(delta_val / price, 6)",
            f"{indent}else:",
            f"{indent}    qty = math.floor(delta_val / price)",
        ]
        lines[target_idx] = "\n".join(new_block)

        # Bloc SELL
        for j in range(target_idx + 1, min(target_idx + 10, len(lines))):
            if "if side ==" in lines[j] and "sell" in lines[j]:
                k = j + 1
                if k < len(lines) and "int(min(qty" in lines[k] and "math.floor(held_qty)" in lines[k]:
                    new_sell = [
                        f"{indent}    if is_crypto:",
                        f"{indent}        qty = min(qty, round(held_qty, 6))",
                        f"{indent}    else:",
                        f"{indent}        qty = int(min(qty, math.floor(held_qty)))",
                    ]
                    lines[k] = "\n".join(new_sell)
                    print(f"[A] Bloc SELL adapte crypto en L{k+1}")
                break

        # Test "if qty <= 0"
        for j in range(target_idx + 1, min(target_idx + 15, len(lines))):
            if re.match(r"^\s+if\s+qty\s*<=\s*0\s*:", lines[j]):
                m2 = re.match(r"^(\s+)", lines[j])
                ind = m2.group(1) if m2 else "        "
                new_test = [
                    f"{ind}# Jalon 3 - seuil min adaptatif",
                    f"{ind}min_qty = 0.0001 if is_crypto else 1",
                    f"{ind}if qty < min_qty:",
                ]
                lines[j] = "\n".join(new_test)
                print(f"[A] Test 'if qty <= 0' remplace par seuil adaptatif en L{j+1}")
                break

        new_src = "\n".join(lines) + ("\n" if src.endswith("\n") else "")
        ee_path.write_text(new_src, encoding="utf-8")
        print("[A] Fichier execution_engine.py reecrit")

# =====================================================================
# B. portfolio_construction_agent.py - _fetch_log_returns + Sharpe reel
# =====================================================================
print()
print("=" * 60)
print("B. portfolio_construction_agent.py - helper + Sharpe")
print("=" * 60)

pca_path = ROOT / "portfolio_construction_agent.py"
psrc = pca_path.read_text(encoding="utf-8", errors="ignore")

# B.1 Verifier que math est importe (sinon ajouter)
if "import math" not in psrc:
    psrc = "import math\n" + psrc
    print("[B0] 'import math' ajoute en tete")

if "# Jalon 3 - Sharpe annualise" in psrc:
    print("[B] Deja applique (skip)")
else:
    plines = psrc.splitlines(keepends=False)

    # Trouve def compute_realized_score
    target_idx = None
    for i, line in enumerate(plines):
        if re.match(r"^def\s+compute_realized_score\s*\(", line):
            target_idx = i
            break

    if target_idx is None:
        print("[B] def compute_realized_score introuvable")
    else:
        print(f"[B] Fonction compute_realized_score trouvee L{target_idx+1}")
        # Cherche la fin
        end_idx = target_idx + 1
        for j in range(target_idx + 1, len(plines)):
            if plines[j].startswith("def ") or (plines[j].startswith("#") and "===" in plines[j]):
                end_idx = j
                break

        # Nouveau bloc : helper + fonction reelle
        new_block = [
            "def _fetch_log_returns(conn, ticker: str, days: int = 90):",
            '    """Jalon 3 - recupere les log-returns des `days` derniers jours de cloture."""',
            "    cur = conn.cursor()",
            "    cur.execute(",
            '        "SELECT p.close FROM prices p "',
            '        "JOIN instruments i ON i.id = p.instrument_id "',
            '        "WHERE i.ticker = ? "',
            '        "ORDER BY p.date DESC LIMIT ?",',
            "        (ticker, days + 1),",
            "    )",
            "    rows = cur.fetchall()",
            "    closes = [r[0] for r in rows if r and r[0] is not None and r[0] > 0]",
            "    closes.reverse()  # chronologique",
            "    if len(closes) < 2:",
            "        return []",
            "    log_returns = []",
            "    for i in range(1, len(closes)):",
            "        prev, cur_p = closes[i-1], closes[i]",
            "        if prev > 0 and cur_p > 0:",
            "            log_returns.append(math.log(cur_p / prev))",
            "    return log_returns",
            "",
            "",
            "def compute_realized_score(conn, ticker: str, days: int = 90) -> float:",
            '    """Jalon 3 - Sharpe annualise sur log-returns des `days` derniers jours.',
            "",
            "    Formule : R = mean(log_returns) / std(log_returns) * sqrt(252)",
            "    Capped a [-3, +3]. Renvoie 0.5 (neutre) si data insuffisante.",
            '    """',
            "    try:",
            "        log_returns = _fetch_log_returns(conn, ticker, days=days)",
            "    except Exception as e:",
            '        print(f"[score_R] {ticker} erreur fetch returns : {e}")',
            "        return 0.5",
            "",
            "    if not log_returns or len(log_returns) < 5:",
            '        print(f"[score_R] {ticker:<6} data insuffisante n={len(log_returns) if log_returns else 0} -> 0.5")',
            "        return 0.5",
            "",
            "    n = len(log_returns)",
            "    mean = sum(log_returns) / n",
            "    var = sum((x - mean) ** 2 for x in log_returns) / n",
            "    std = math.sqrt(var)",
            "",
            "    if std < 1e-9:",
            '        print(f"[score_R] {ticker:<6} std nulle n={n} -> 0.5")',
            "        return 0.5",
            "",
            "    sharpe = mean / std * math.sqrt(252)",
            "    sharpe = max(-3.0, min(3.0, sharpe))",
            '    print(f"[score_R] {ticker:<6} n={n:>2} mean={mean:+.5f} std={std:.5f} sharpe={sharpe:+.3f}")',
            "    return sharpe",
            "",
        ]

        plines[target_idx:end_idx] = new_block
        new_psrc = "\n".join(plines) + ("\n" if psrc.endswith("\n") else "")
        pca_path.write_text(new_psrc, encoding="utf-8")
        print(f"[B] Stub remplace + helper ajoute, end_idx etait L{end_idx+1}")

# =====================================================================
# C. DB : enable_realized = 1
# =====================================================================
print()
print("=" * 60)
print("C. DB - enable_realized = 1")
print("=" * 60)

con = sqlite3.connect(ROOT / "thesium.db")
cur = con.cursor()
try:
    cur.execute("PRAGMA table_info(target_construction_config)")
    cols = [c[1] for c in cur.fetchall()]
    if "enable_realized" in cols:
        cur.execute("UPDATE target_construction_config SET enable_realized=1 WHERE id=1")
        con.commit()
        cur.execute("SELECT enable_realized FROM target_construction_config WHERE id=1")
        v = cur.fetchone()
        print(f"[C] enable_realized = {v[0] if v else 'NULL'}")
    else:
        print(f"[C] Pas de colonne enable_realized - cols dispo : {cols}")
        cur.execute("SELECT * FROM target_construction_config WHERE id=1")
        r = cur.fetchone()
        if r:
            col_names = [d[0] for d in cur.description]
            for cn, val in zip(col_names, r):
                print(f"    {cn:<25} = {val}")
except Exception as e:
    print(f"[C] Erreur : {e}")
con.close()

print()
print("=" * 60)
print("PATCHS APPLIQUES")
print("=" * 60)
'@

$tmpPy = "$env:TEMP\_crypto_v3.py"
$patchPy | Set-Content -Path $tmpPy -Encoding UTF8

Write-Host ""
Write-Host "[2/5] Application des patchs..." -ForegroundColor Yellow
py $tmpPy

# Verification execution_engine
Write-Host ""
Write-Host "[3/5] Verification execution_engine L1438-1478..." -ForegroundColor Yellow
$verifyPy = @'
from pathlib import Path
src = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py").read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()
for i in range(1438, 1478):
    if i < len(lines):
        print(f"  L{i+1}  {lines[i]}")
'@
$tmpVer = "$env:TEMP\_verify_v3.py"
$verifyPy | Set-Content -Path $tmpVer -Encoding UTF8
py $tmpVer

# Verification PCA
Write-Host ""
Write-Host "[4/5] Verification PCA L268-330..." -ForegroundColor Yellow
$verifyPca = @'
from pathlib import Path
src = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py").read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()
for i in range(268, 335):
    if i < len(lines):
        print(f"  L{i+1}  {lines[i]}")
'@
$tmpVerP = "$env:TEMP\_verify_pca_v3.py"
$verifyPca | Set-Content -Path $tmpVerP -Encoding UTF8
py $tmpVerP

# Smoke test : import du module et appel sur AAPL/BTC
Write-Host ""
Write-Host "[5/5] Smoke test : import + appel compute_realized_score..." -ForegroundColor Yellow
$smokePy = @'
import sys, sqlite3
sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
try:
    from portfolio_construction_agent import compute_realized_score, _fetch_log_returns
    print("[SMOKE] Import OK")
except Exception as e:
    print(f"[SMOKE] Import KO : {e}")
    sys.exit(1)

con = sqlite3.connect(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
for ticker in ["AAPL", "BTC", "ETH", "MSFT", "META"]:
    try:
        lr = _fetch_log_returns(con, ticker, days=90)
        r = compute_realized_score(con, ticker, days=90)
        print(f"  {ticker:<6} n_returns={len(lr):>2}  R={r:+.4f}")
    except Exception as e:
        print(f"  {ticker:<6} ERREUR : {e}")
con.close()
'@
$tmpSmoke = "$env:TEMP\_smoke_v3.py"
$smokePy | Set-Content -Path $tmpSmoke -Encoding UTF8
py $tmpSmoke

Write-Host ""
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "  TERMINE - Verifie les 3 sections ci-dessus" -ForegroundColor Cyan
Write-Host "  Prochaine etape : enrichissement prix 90j" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
