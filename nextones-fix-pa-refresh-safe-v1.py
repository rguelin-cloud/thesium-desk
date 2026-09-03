# -*- coding: utf-8 -*-
# [FIX_PA_REFRESH_SAFE_V1]
# Sandboxe les appels refreshDashboard() et renderKPIs() dans _paExecute / _paReject
# pour ne plus afficher "Cannot read properties of undefined (reading 'portfolio')"
# quand le fill a deja reussi cote backend.
# Idempotent. Backup .bak. Modifie app.js uniquement.
import io, os, ast, time, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TS = time.strftime("%Y%m%d-%H%M%S")
MARKER = "/* [FIX_PA_REFRESH_SAFE_V1] */"

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

target = os.path.join(ROOT, "app.js")
src = read_utf8(target)

if MARKER in src:
    print("[app.js] SKIP (marker present)")
    sys.exit(0)

backup(target)

# Remplacement 1 : ligne L7140-7141 dans _paExecute
old_block_exec = (
    '        renderPendingApprovals();\n'
    '        if (typeof refreshDashboard === "function") refreshDashboard();\n'
    '        if (typeof renderKPIs === "function") renderKPIs();\n'
)
new_block_exec = (
    '        renderPendingApprovals();\n'
    '        ' + MARKER + '\n'
    '        try { if (typeof refreshDashboard === "function") { var _r1 = refreshDashboard(); if (_r1 && typeof _r1.catch === "function") _r1.catch(function(e){console.warn("refreshDashboard:", e);}); } } catch (_e1) { console.warn("refreshDashboard sync:", _e1); }\n'
    '        try { if (typeof renderKPIs === "function") { var _r2 = renderKPIs(); if (_r2 && typeof _r2.catch === "function") _r2.catch(function(e){console.warn("renderKPIs:", e);}); } } catch (_e2) { console.warn("renderKPIs sync:", _e2); }\n'
)

if old_block_exec not in src:
    print("FAIL: bloc d'origine _paExecute introuvable")
    sys.exit(1)

new_src = src.replace(old_block_exec, new_block_exec, 1)

# Petite verif ASCII de l'insertion (le fichier hote a probablement des accents, on s'en fout)
inj_added = new_block_exec
bad = [(i, ord(c)) for i, c in enumerate(inj_added) if ord(c) > 127]
if bad:
    print("FAIL: injection non-ASCII -> %r" % bad[:5])
    sys.exit(1)
print("  injection ASCII pur OK")

# Pas de validation AST (c'est du JS, pas du Python).
# On verifie juste que le marker est present et que la longueur est plausible.
if MARKER not in new_src:
    print("FAIL: marker absent apres replace")
    sys.exit(1)
if len(new_src) <= len(src):
    print("FAIL: new file smaller than old")
    sys.exit(1)

write_utf8(target, new_src)
print("  written: %d -> %d bytes (+%d)" % (len(src), len(new_src), len(new_src) - len(src)))
print("[app.js] OK")
print("\n[DONE] FIX_PA_REFRESH_SAFE_V1 deploye")
print("  -> hard refresh navigateur (Ctrl+F5) puis re-cliquer Execute")
