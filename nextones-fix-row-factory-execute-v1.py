# -*- coding: utf-8 -*-
# [FIX_ROW_FACTORY_EXECUTE_V1]
# _update_position et autres acces dict-style sur fetchone() necessitent
# conn.row_factory = sqlite3.Row dans les endpoints execute/reject.
# Patch idempotent. Marker en commentaire. Backup .bak.<ts>.
import io, os, re, ast, py_compile, time, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TS = time.strftime("%Y%m%d-%H%M%S")
MARKER = "# [FIX_ROW_FACTORY_EXECUTE_V1]"

def read_utf8(p):
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()

def write_utf8(p, content):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)

def backup(p):
    bk = p + ".bak." + TS
    with io.open(p, "rb") as fr, io.open(bk, "wb") as fw:
        fw.write(fr.read())
    print("  backup -> " + os.path.basename(bk))

target = os.path.join(ROOT, "api_server_with_static.py")
src = read_utf8(target)

if MARKER in src:
    print("[api_server_with_static.py] SKIP (marker present)")
    sys.exit(0)

backup(target)

# On cherche les 2 ouvertures dans les endpoints execute/reject :
#   conn = _sql.connect(_db, timeout=30)
#   conn.execute("PRAGMA busy_timeout=30000")
# et on injecte juste apres :
#   conn.row_factory = _sql.Row  # [FIX_ROW_FACTORY_EXECUTE_V1]
pattern = re.compile(
    r'(conn\s*=\s*_sql\.connect\(_db,\s*timeout=30\)\s*\n\s*conn\.execute\(\s*"PRAGMA busy_timeout=30000"\s*\)\s*\n)',
    re.MULTILINE,
)
matches = list(pattern.finditer(src))
print("  matches found: %d" % len(matches))
if len(matches) < 1:
    print("FAIL: aucun pattern conn = _sql.connect(_db, timeout=30) + PRAGMA trouve")
    sys.exit(1)

# Inject en reverse (preserve indices)
new_src = src
for m in reversed(matches):
    inject = '        conn.row_factory = _sql.Row  ' + MARKER + '\n'
    new_src = new_src[:m.end()] + inject + new_src[m.end():]

# Verifier que l'injection est ASCII pure (le fichier hote peut avoir des accents)
bad = [(i, ord(c)) for i, c in enumerate(inject) if ord(c) > 127]
if bad:
    print("FAIL: inject non-ASCII -> %r" % bad[:5])
    sys.exit(1)
print("  inject ASCII pur OK (%d chars)" % len(inject))

# AST + py_compile
try:
    ast.parse(new_src)
    print("  ast.parse OK")
except SyntaxError as e:
    print("FAIL ast.parse: %s" % e)
    sys.exit(1)

write_utf8(target, new_src)
py_compile.compile(target, doraise=True)
print("  py_compile OK")
print("[api_server_with_static.py] OK (%d injections)" % len(matches))

print("\n[DONE] FIX_ROW_FACTORY_EXECUTE_V1 deploye")
print("  -> restart API + re-clic Execute sur #343")
