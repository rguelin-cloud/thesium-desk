# [FIX_CYCLE_LOCK_V3] Verrou 1 cycle / jour sur POST /api/run-agents
# V3 : regex tolerante aux parentheses imbriquees (Depends(...), Query(...))
# Marqueur : [CYCLE_LOCK_V1]
$ErrorActionPreference = "Stop"
$target = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
$db     = "C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
$backup = "$target.bak_cyclelock_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

if (-not (Test-Path $target)) { Write-Host "[ERR] $target introuvable" -ForegroundColor Red; exit 1 }
Copy-Item $target $backup -Force
Write-Host "[BACKUP] $backup" -ForegroundColor Cyan

# 1. Bloc Python guard (fichier separe)
$guardFile = Join-Path $env:TEMP "cycle_lock_guard_v3_$(Get-Random).txt"
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

# 2. Helper Python avec parsing parentheses balance (pas regex)
$helper = Join-Path $env:TEMP "cycle_lock_v3_$(Get-Random).py"
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

# 2. Ajouter Query a 'from fastapi import' si absent
m_imp = re.search(r"from fastapi import ([^\n]+)", src)
if m_imp:
    imports = m_imp.group(1)
    if "Query" not in imports:
        new_imports = imports.rstrip() + ", Query"
        src = src[:m_imp.start(1)] + new_imports + src[m_imp.end(1):]
        print("[IMP] Query ajoute a 'from fastapi import'")

# 3. Localiser "def run_agents_endpoint(" et parser les parentheses a la main
needle = "def run_agents_endpoint"
idx = src.find(needle)
if idx < 0:
    print("[ERR] 'def run_agents_endpoint' introuvable")
    sys.exit(2)

# Trouver la '(' juste apres
paren_open = src.find("(", idx)
if paren_open < 0:
    print("[ERR] '(' apres def introuvable")
    sys.exit(2)

# Balance des parentheses
depth = 0
i = paren_open
while i < len(src):
    c = src[i]
    if c == "(":
        depth += 1
    elif c == ")":
        depth -= 1
        if depth == 0:
            paren_close = i
            break
    i += 1
else:
    print("[ERR] parenthese fermante introuvable")
    sys.exit(2)

# Trouver le ':' juste apres
colon_pos = src.find(":", paren_close)
if colon_pos < 0:
    print("[ERR] ':' apres ) introuvable")
    sys.exit(2)

# Trouver le '\n' apres le ':'
nl_pos = src.find("\n", colon_pos)
if nl_pos < 0:
    print("[ERR] newline apres ':' introuvable")
    sys.exit(2)

# Extraire les parametres actuels
current_params = src[paren_open + 1: paren_close].strip()
print(f"[INFO] Signature trouvee : def run_agents_endpoint({current_params})")
print(f"[INFO] def_start={idx} paren_open={paren_open} paren_close={paren_close} colon={colon_pos} nl={nl_pos}")

# 4. Ajouter "force: bool = Query(...)" si absent
if "force" not in current_params:
    new_params = current_params.rstrip(", ") + ", force: bool = Query(False, description='Bypass verrou 1/jour')"
    src = src[:paren_open + 1] + new_params + src[paren_close:]
    print("[SIG] Parametre force ajoute")
    # Recalculer positions apres modif
    needle = "def run_agents_endpoint"
    idx = src.find(needle)
    paren_open = src.find("(", idx)
    depth = 0
    i = paren_open
    while i < len(src):
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                paren_close = i
                break
        i += 1
    colon_pos = src.find(":", paren_close)
    nl_pos = src.find("\n", colon_pos)
else:
    print("[INFO] Parametre force deja present")

# 5. Position d'insertion = juste apres le '\n' qui suit ':'
insert_pos = nl_pos + 1

# 6. Detecter indentation du corps
after = src[insert_pos:insert_pos + 2000]
indent_match = re.match(r"([ \t]+)\S", after)
if not indent_match:
    print("[ERR] indent corps introuvable")
    sys.exit(5)
indent = indent_match.group(1)
print(f"[INFO] Indentation corps : {len(indent)} espaces")

# 7. Charger guard et indenter
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
    # Extraire les 5 lignes autour
    lines = src.splitlines()
    start = max(0, e.lineno - 3)
    end = min(len(lines), e.lineno + 3)
    for i in range(start, end):
        print(f"  L{i+1}: {lines[i]}")
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
