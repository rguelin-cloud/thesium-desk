# regen_snapshot_with_R.ps1
# 1. Active enable_realized=1 dans target_construction_config
# 2. Lance run_construction_agent manuellement
# 3. Verifie le nouveau snapshot a des R_norm != 0.5

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$db = "$root\thesium.db"

Write-Host "=== ETAPE 1 : Activer enable_realized=1 ===" -ForegroundColor Cyan

$py1 = @'
import sqlite3
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

# Lire config actuelle
cur.execute("SELECT id, params_json FROM target_construction_config ORDER BY id DESC LIMIT 1")
row = cur.fetchone()
if not row:
    print("[ERR] target_construction_config vide")
    sys.exit(1)

config_id, params_json = row
params = json.loads(params_json) if params_json else {}
print(f"[INFO] config_id={config_id}")
print(f"[BEFORE] enable_realized = {params.get('enable_realized', 'MISSING')}")
print(f"[BEFORE] w_realized      = {params.get('w_realized', 'MISSING')}")

# Activer
params["enable_realized"] = 1
# w_realized reste a 0.15 (deja OK)

new_json = json.dumps(params, ensure_ascii=False)
cur.execute("UPDATE target_construction_config SET params_json=? WHERE id=?", (new_json, config_id))
con.commit()

# Verif
cur.execute("SELECT params_json FROM target_construction_config WHERE id=?", (config_id,))
check = json.loads(cur.fetchone()[0])
print(f"[AFTER]  enable_realized = {check['enable_realized']}")
print(f"[AFTER]  w_realized      = {check['w_realized']}")

con.close()
print("[OK] Config mise a jour")
'@

$tmp1 = "$env:TEMP\enable_realized.py"
[System.IO.File]::WriteAllText($tmp1, $py1, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] Activation enable_realized echouee" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== ETAPE 2 : Lancer run_construction_agent ===" -ForegroundColor Cyan

$py2 = @'
import sys
import io
import os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
os.chdir(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

import sqlite3
from portfolio_construction_agent_jalon2 import run_construction_agent

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

# cycle_id : on en cree un synthetique pour l'audit
from datetime import datetime
cycle_id = f"snap_regen_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

print(f"[INFO] Lancement run_construction_agent cycle_id={cycle_id}")
try:
    result = run_construction_agent(con, cycle_id=cycle_id)
    print(f"[OK] snapshot_id = {result.get('snapshot_id')}")
    print(f"[OK] n_targets   = {result.get('n_targets')}")
    scores = result.get('scores', {})
    print(f"[OK] scores (sample) :")
    for t, s in list(scores.items())[:5]:
        print(f"     {t} : {s}")
except Exception as e:
    import traceback
    print(f"[ERR] run_construction_agent a echoue : {e}")
    traceback.print_exc()
    con.close()
    sys.exit(1)

con.close()
'@

$tmp2 = "$env:TEMP\regen_snapshot.py"
[System.IO.File]::WriteAllText($tmp2, $py2, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp2
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERR] run_construction_agent a echoue" -ForegroundColor Red
    exit 2
}

Write-Host ""
Write-Host "=== ETAPE 3 : Verifier nouveau snapshot ===" -ForegroundColor Cyan

$py3 = @'
import sqlite3
import json
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

cur.execute("""
    SELECT snapshot_id, COUNT(*), MIN(created_at)
    FROM portfolio_targets_history
    GROUP BY snapshot_id
    ORDER BY MIN(created_at) DESC
    LIMIT 3
""")
print("[INFO] 3 derniers snapshots :")
for r in cur.fetchall():
    print(f"  {r[0]:42s}  n={r[1]:3d}  ts={r[2]}")

# Dernier snapshot
cur.execute("""
    SELECT snapshot_id FROM portfolio_targets_history
    ORDER BY created_at DESC LIMIT 1
""")
last = cur.fetchone()[0]
print(f"\n[INFO] Dernier snapshot : {last}")
print(f"[INFO] Components_json par ticker :\n")

cur.execute("""
    SELECT ticker, score, components_json
    FROM portfolio_targets_history
    WHERE snapshot_id = ?
    ORDER BY ticker
""", (last,))

r_norm_values = []
for ticker, score, comp in cur.fetchall():
    if comp:
        try:
            d = json.loads(comp)
            r = d.get("R_norm")
            if r is not None:
                r_norm_values.append(r)
            print(f"  {ticker:6s} score={score:.4f}  R_norm={d.get('R_norm')}  C_norm={d.get('C_norm')}  M_norm={d.get('M_norm')}")
        except Exception as e:
            print(f"  {ticker} parse error : {e}")

# Verif R_norm non figes a 0.5
unique_r = set(r_norm_values)
print(f"\n[CHECK] R_norm uniques : {sorted(unique_r)}")
if len(unique_r) == 1 and 0.5 in unique_r:
    print("[FAIL] Tous les R_norm = 0.5 (toujours figes !)")
    sys.exit(3)
else:
    print(f"[OK] R_norm varies sur {len(unique_r)} valeurs distinctes -> compute_realized_score actif !")

con.close()
'@

$tmp3 = "$env:TEMP\verif_snapshot.py"
[System.IO.File]::WriteAllText($tmp3, $py3, (New-Object System.Text.UTF8Encoding $false))
& py -3.13 $tmp3
$rc = $LASTEXITCODE

Write-Host ""
if ($rc -eq 0) {
    Write-Host "=== SNAPSHOT REGENERE AVEC R ACTIF ===" -ForegroundColor Green
    Write-Host "Le prochain cycle utilisera le nouveau snapshot." -ForegroundColor White
} else {
    Write-Host "[WARN] R_norm encore figes - voir output ci-dessus" -ForegroundColor Yellow
}
