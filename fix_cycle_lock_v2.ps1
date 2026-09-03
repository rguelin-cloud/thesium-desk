# [FIX_CYCLE_LOCK_V2] Verrou 1 cycle / jour sur POST /api/run-agents
# V2 : regex adaptee a la signature reelle :
#   @app.post("/api/run-agents")
#   @limiter.limit("3/minute")
#   def run_agents_endpoint(request: Request, user: dict = Depends(require_manager)):
# Marqueur : [CYCLE_LOCK_V1]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$db     = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
$backup = "$target.bak_cyclelock_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Bloc Python a injecter (fichier separe pour eviter f-string emboitees)
$guardFile = Join-Path $env:TEMP "cycle_lock_guard_v2_$(Get-Random).txt"
$guardBlock = @'
# [CYCLE_LOCK_V1] Verrou 1 cycle / jour avec override ?force=true
import sqlite3 as _sqlite_lock
from datetime import datetime as _dt_lock
from pathlib import Path as _Path_lock
_lock_db_path = _Path_lock(__file__).resolve().parent / "thesium.db"
_today_str = _dt_lock.now().strftime("%Y-%m-%d")
_cx_lock = _sqlite_lock.connect(str(_lock_db_path), timeout=10)
_cx_lock.row_factory = _sqlite_lock.Row
try:
    _existing_cycle = _cx_lock.execute(
        "SELECT cycle_id, started_at, forced FROM cycles_daily WHERE cycle_date = ?",
        (_today_str,)
    ).fetchone()
    if _existing_cycle and not force:
        from fastapi import HTTPException as _HE_lock
        _msg = "Cycle deja fait aujourd hui (" + str(_existing_cycle["cycle_id"]) + " a " + str(_existing_cycle["started_at"]) + "). Utilisez ?force=true pour relancer."
        raise _HE_lock(status_code=409, detail={
            "code": "CYCLE_ALREADY_DONE",
            "message": _msg,
            "cycle_id": _existing_cycle["cycle_id"],
            "started_at": _existing_cycle["started_at"],
        })
    _cycle_id_lock = _dt_lock.now().strftime("%Y%m%d-%H%M%S")
    _note_lock = "forced via ?force=true" if force else "auto/manual normal"
    _cx_lock.execute(
        "INSERT OR REPLACE INTO cycles_daily (cycle_date, cycle_id, started_at, forced, note) VALUES (?, ?, datetime('now'), ?, ?)",
        (_today_str, _cycle_id_lock, 1 if force else 0, _note_lock)
    )
    _cx_lock.commit()
finally:
    _cx_lock.close()
'@
Set-Content -Path $guardFile -Value $guardBlock -Encoding UTF8

# 2. Helper Python : regex tolerante aux multiples decorateurs
$helper = Join-Path $env:TEMP "cycle_lock_v2_$(Get-Random).py"
$helperCode = @'
import re, sys, ast, sqlite3, textwrap
from pathlib import Path

target = Path(sys.argv[1])
backup = Path(sys.argv[2])
db_path = Path(sys.argv[3])
guard_file = Path(sys.argv[4])

src = target.read_text(encoding="utf-8-sig")
MARKER = "[CYCLE_LOCK_V1]"

if MARKER in src:
    print(f"[SKIP] {MARKER} deja present")
    sys.exit(0)

# 1. Creer table cycles_daily
cx = sqlite3.connect(str(db_path), timeout=10)
try:
    cx.execute("""
        CREATE TABLE IF NOT EXISTS cycles_daily (
            cycle_date TEXT PRIMARY KEY,
            cycle_id TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            ended_at TEXT,
            forced INTEGER NOT NULL DEFAULT 0,
            agents_result TEXT,
            note TEXT
        )
    """)
    cx.commit()
    print("[DB] Table cycles_daily prete")
finally:
    cx.close()

# 2. S'assurer que Query est importe depuis fastapi
m_imp = re.search(r"from fastapi import ([^\n]+)", src)
if m_imp:
    imports = m_imp.group(1)
    if "Query" not in imports:
        new_imports = imports.rstrip() + ", Query"
        src = src[:m_imp.start(1)] + new_imports + src[m_imp.end(1):]
        print("[IMP] Query ajoute a 'from fastapi import'")

# 3. Localiser la fonction run_agents_endpoint (tolerant aux decorateurs multiples)
# Pattern : capture jusqu'a "def run_agents_endpoint(" + ses parametres + ":" + newline
m = re.search(
    r"(def\s+run_agents_endpoint\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:\s*\n)",
    src
)
if not m:
    print("[ERR] def run_agents_endpoint introuvable")
    sys.exit(2)

full_def = m.group(1)
current_params = m.group(2).strip()
print(f"[INFO] Signature trouvee : def run_agents_endpoint({current_params})")

# 4. Ajouter "force: bool = Query(False, ...)" si absent
if "force" not in current_params:
    if current_params:
        new_params = current_params.rstrip(", ") + ", force: bool = Query(False, description='Bypass verrou 1/jour')"
    else:
        new_params = "force: bool = Query(False, description='Bypass verrou 1/jour')"
    new_def = f"def run_agents_endpoint({new_params}):\n"
    src = src[:m.start(1)] + new_def + src[m.end(1):]
    print("[SIG] Parametre force ajoute")
else:
    print("[INFO] Parametre force deja present")

# 5. Re-localiser apres modif
m2 = re.search(
    r"def\s+run_agents_endpoint\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:\s*\n",
    src
)
if not m2:
    print("[ERR] re-localisation echouee")
    sys.exit(4)
insert_pos = m2.end()

# 6. Detecter l'indentation du corps
after = src[insert_pos:insert_pos + 2000]
indent_match = re.match(r"([ \t]+)\S", after)
if not indent_match:
    print("[ERR] indent corps introuvable")
    sys.exit(5)
indent = indent_match.group(1)
print(f"[INFO] Indentation corps : {len(indent)} espaces")

# 7. Charger le bloc guard et l'indenter
guard_raw = guard_file.read_text(encoding="utf-8-sig").strip("\n")
guard_indented = textwrap.indent(guard_raw, indent) + "\n"

# 8. Inserer
src = src[:insert_pos] + guard_indented + src[insert_pos:]

# 9. Validation AST
try:
    ast.parse(src)
except SyntaxError as e:
    target.write_bytes(backup.read_bytes())
    print(f"[AST-FAIL] ligne {e.lineno}: {e.msg}")
    sys.exit(3)

target.write_text(src, encoding="utf-8")
print(f"[OK] {MARKER} applique sur run_agents_endpoint")
print("[AST-OK]")
'@

Set-Content -Path $helper -Value $helperCode -Encoding UTF8
py -3.13 $helper $target $backup $db $guardFile
$rc = $LASTEXITCODE
Remove-Item $guardFile -Force -ErrorAction SilentlyContinue
Remove-Item $helper -Force -ErrorAction SilentlyContinue

if ($rc -ne 0) {
    Write-Host "[ROLLBACK] Restoration depuis $backup" -ForegroundColor Yellow
    Copy-Item $backup $target -Force
    exit $rc
}

Write-Host "[DONE] Verrou cycle 1/jour actif sur POST /api/run-agents" -ForegroundColor Green
Write-Host "  - Refus 409 si cycle deja fait aujourd hui" -ForegroundColor Gray
Write-Host "  - Bypass : POST /api/run-agents?force=true" -ForegroundColor Gray
Write-Host "  - Audit : table cycles_daily" -ForegroundColor Gray
