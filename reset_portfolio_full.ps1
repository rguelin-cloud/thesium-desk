# reset_portfolio_full.ps1
# Reset complet trading : positions + ordres + historique + reconciliation
# Garde : targets, target_universe, instruments, prices, theses, target_construction_config, users, risk_config
# Cash initial : 1 000 000 EUR

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$db = Join-Path $root "thesium.db"

if (-not (Test-Path $db)) {
    Write-Host "[KO] DB introuvable : $db" -ForegroundColor Red
    exit 1
}

# ============================================================
# 1) BACKUP
# ============================================================
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = Join-Path $root "_backups_reset"
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir | Out-Null
}
$backupDb = Join-Path $backupDir "thesium.db.bak.$ts"
$backupSql = Join-Path $backupDir "thesium.sql.dump.$ts"

Copy-Item $db $backupDb -Force
Write-Host "[OK] Backup binaire : $backupDb" -ForegroundColor Green

# Dump SQL complet via sqlite3 si dispo, sinon via Python
$sqlite3Exe = (Get-Command sqlite3 -ErrorAction SilentlyContinue)
if ($sqlite3Exe) {
    & sqlite3 $db ".dump" | Out-File -FilePath $backupSql -Encoding utf8
    Write-Host "[OK] Dump SQL : $backupSql" -ForegroundColor Green
} else {
    Write-Host "[INFO] sqlite3.exe absent, dump SQL via Python" -ForegroundColor Yellow
    $py = @"
import sqlite3
c = sqlite3.connect(r'$db')
with open(r'$backupSql', 'w', encoding='utf-8') as f:
    for line in c.iterdump():
        f.write(line + '\n')
c.close()
print('OK dump Python')
"@
    $tmp = Join-Path $env:TEMP "dump_$ts.py"
    [System.IO.File]::WriteAllText($tmp, $py, (New-Object System.Text.UTF8Encoding $false))
    py -3.13 $tmp
    Remove-Item $tmp -Force
}

# ============================================================
# 2) RESET via Python
# ============================================================
Write-Host "`n=== RESET du portefeuille ===" -ForegroundColor Cyan

$pyReset = @'
import sqlite3, sys
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
INITIAL_CASH = 1_000_000.0

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

# Etat AVANT
print("=" * 60)
print("ETAT AVANT RESET")
print("=" * 60)
for t in ["portfolio_positions", "orders", "fills", "portfolio_history",
          "portfolio_state", "cycle_reconciliation_log", "exit_decisions_log",
          "theses", "portfolio_targets", "portfolio_targets_history",
          "ic_memos", "event_log", "regime_log", "prices", "instruments"]:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<35} {n} rows")
    except Exception as e:
        print(f"  {t:<35} ERR: {e}")

print()
print("=" * 60)
print("PURGE des tables trading")
print("=" * 60)
# Tables a vider (reset trading)
tables_to_clear = [
    "portfolio_positions",
    "orders",
    "fills",
    "portfolio_history",
    "portfolio_state",
    "cycle_reconciliation_log",
    "exit_decisions_log",
    "ic_memos",
    "regime_log",
    "event_log",
]
for t in tables_to_clear:
    try:
        c.execute(f"DELETE FROM {t}")
        # reset sequence si presente
        c.execute("DELETE FROM sqlite_sequence WHERE name = ?", (t,))
        print(f"  [PURGE] {t}")
    except Exception as e:
        print(f"  [SKIP] {t} ({e})")

# Etat initial cash dans portfolio_state
# Schema typique : (id, cash, nav, ...). On essaie ; sinon on insere generique.
print()
print("=" * 60)
print(f"INIT portfolio_state avec cash = {INITIAL_CASH}")
print("=" * 60)
cols = [r["name"] for r in c.execute("PRAGMA table_info(portfolio_state)")]
print(f"  colonnes portfolio_state: {cols}")

# Insert minimal
data = {}
if "cash" in cols:
    data["cash"] = INITIAL_CASH
if "nav" in cols:
    data["nav"] = INITIAL_CASH
if "total_value" in cols:
    data["total_value"] = INITIAL_CASH
if "invested_value" in cols:
    data["invested_value"] = 0.0
if "invested_pct" in cols:
    data["invested_pct"] = 0.0
if "cash_pct" in cols:
    data["cash_pct"] = 100.0
if "updated_at" in cols:
    from datetime import datetime
    data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
if "created_at" in cols:
    from datetime import datetime
    data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

if data:
    keys = ", ".join(data.keys())
    placeholders = ", ".join(["?"] * len(data))
    c.execute(f"INSERT INTO portfolio_state ({keys}) VALUES ({placeholders})",
              tuple(data.values()))
    print(f"  [INSERT] portfolio_state row : {data}")
else:
    print("  [WARN] aucune colonne reconnue dans portfolio_state")

# Snapshot initial portfolio_history (point de depart)
cols_h = [r["name"] for r in c.execute("PRAGMA table_info(portfolio_history)")]
print(f"  colonnes portfolio_history: {cols_h}")
data_h = {}
    # [RESET_DATE_FIX_V1] colonne 'date' NOT NULL obligatoire
    from datetime import date as _date_today
    if "date" in cols_h: data_h["date"] = _date_today.today().isoformat()
if "cash" in cols_h: data_h["cash"] = INITIAL_CASH
if "nav" in cols_h: data_h["nav"] = INITIAL_CASH
if "total_value" in cols_h: data_h["total_value"] = INITIAL_CASH
if "invested_value" in cols_h: data_h["invested_value"] = 0.0
if "ts" in cols_h:
    from datetime import datetime
    data_h["ts"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
elif "created_at" in cols_h:
    from datetime import datetime
    data_h["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

if data_h:
    keys = ", ".join(data_h.keys())
    placeholders = ", ".join(["?"] * len(data_h))
    try:
        c.execute(f"INSERT INTO portfolio_history ({keys}) VALUES ({placeholders})",
                  tuple(data_h.values()))
        print(f"  [INSERT] portfolio_history row : {data_h}")
    except Exception as e:
        print(f"  [WARN] portfolio_history insert : {e}")

c.commit()

print()
print("=" * 60)
print("ETAT APRES RESET")
print("=" * 60)
for t in ["portfolio_positions", "orders", "fills", "portfolio_history",
          "portfolio_state", "cycle_reconciliation_log", "exit_decisions_log",
          "theses", "portfolio_targets", "portfolio_targets_history",
          "prices", "instruments"]:
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<35} {n} rows")
    except Exception as e:
        print(f"  {t:<35} ERR: {e}")

print()
print("portfolio_state actuel :")
for r in c.execute("SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1"):
    print(f"  {dict(r)}")

c.close()
print("\n[OK] Reset termine. Cash = 1 000 000 EUR.")
'@

$tmpReset = Join-Path $env:TEMP "reset_$ts.py"
[System.IO.File]::WriteAllText($tmpReset, $pyReset, (New-Object System.Text.UTF8Encoding $false))
py -3.13 $tmpReset
$rc = $LASTEXITCODE
Remove-Item $tmpReset -Force

if ($rc -ne 0) {
    Write-Host "`n[ERREUR] Reset echec (code $rc). Restauration :" -ForegroundColor Red
    Write-Host "  Copy-Item '$backupDb' '$db' -Force" -ForegroundColor Yellow
    exit $rc
}

Write-Host "`n===========================================================" -ForegroundColor Green
Write-Host "RESET TERMINE" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "Backup binaire : $backupDb"
Write-Host "Backup SQL     : $backupSql"
Write-Host ""
Write-Host "Pour annuler le reset :" -ForegroundColor Yellow
Write-Host "  Copy-Item '$backupDb' '$db' -Force"
Write-Host ""
Write-Host "Prochaines etapes :" -ForegroundColor Cyan
Write-Host "  1. Redemarre uvicorn (Ctrl+C + relance)"
Write-Host "  2. Lance run_construction_agent depuis l UI"
Write-Host "  3. Verifie que R_norm reel apparait dans portfolio_targets_history"
Write-Host "  4. Lance un cycle de decision -> BTC BUY 0.258 attendu"
