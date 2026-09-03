# -*- coding: utf-8 -*-
"""
Fix mojibake double-encoding dans :
  - execution_engine.py (5 f-strings + 1 commentaire)
  - memo_generator.py (helper defensif sur les snapshots deja en DB)

Idempotent : marker # [MOJIBAKE_FIX_V1] pose dans les 2 fichiers.

Strategie execution_engine.py :
  remplace les sequences mojibake (encode latin-1 -> decode utf-8 bug)
  par leurs vrais equivalents Unicode :
    'â‰¤' -> '≤'
    'â‰¥' -> '≥'
    'â†'  -> '→' (3-byte mojibake : c3 a2 e2 80 a0 e2 80 99)
    'â†'  -> '→' (autre variante)
    'Ã—' -> '×'
    'Ã©' -> 'é'
    'Ã '  -> 'à'

Strategie memo_generator.py :
  ajoute _fix_mojibake(s) dans _build_convergence_section,
  applique sur 'driver' avant rendu.
"""
import os, sys, io, shutil, ast, py_compile, re, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Table de correspondance mojibake -> clean
# Note : on construit a partir des bytes UTF-8 pour eviter toute corruption du script
MOJI_MAP = [
    # ≤ : utf8 = e2 89 a4. Mojibake (utf8 lu en cp1252 puis re-utf8) = c3a2 e280b0 c2a4
    (b"\xc3\xa2\xe2\x80\xb0\xc2\xa4".decode("utf-8"), "\u2264"),  # ≤
    (b"\xc3\xa2\xe2\x80\xb0\xc2\xa5".decode("utf-8"), "\u2265"),  # ≥
    # → : utf8 = e2 86 92. Mojibake = c3a2 e28086 e28099 (3 chars)
    (b"\xc3\xa2\xe2\x80\xa0\xe2\x80\x99".decode("utf-8"), "\u2192"),  # →
    (b"\xc3\xa2\xe2\x80\xa0\xe2\x80\xa6".decode("utf-8"), "\u2192"),  # variante
    # × : utf8 = c3 97. Mojibake = c3 83 e2 80 94
    (b"\xc3\x83\xe2\x80\x94".decode("utf-8"), "\u00d7"),  # ×
    # é : utf8 = c3 a9. Mojibake = c3 83 c2 a9
    (b"\xc3\x83\xc2\xa9".decode("utf-8"), "\u00e9"),  # é
    (b"\xc3\x83\xc2\xa8".decode("utf-8"), "\u00e8"),  # è
    (b"\xc3\x83\xc2\xa0".decode("utf-8"), "\u00e0"),  # à
    (b"\xc3\x83\xc2\xa2".decode("utf-8"), "\u00e2"),  # â
    (b"\xc3\x83\xc2\xae".decode("utf-8"), "\u00ee"),  # î
    (b"\xc3\x83\xc2\xb4".decode("utf-8"), "\u00f4"),  # ô
    (b"\xc3\x83\xc2\xb9".decode("utf-8"), "\u00f9"),  # ù
    (b"\xc3\x83\xc2\xa7".decode("utf-8"), "\u00e7"),  # ç
]

def apply_moji_fix(s: str) -> tuple[str, int]:
    """Replace tous les mojibake par leur clean. Retourne (str, nb_replace)."""
    total = 0
    for moji, clean in MOJI_MAP:
        cnt = s.count(moji)
        if cnt:
            s = s.replace(moji, clean)
            total += cnt
    return s, total

def backup(fp: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{fp}.bak-mojibake-{ts}"
    shutil.copy2(fp, bak)
    return bak

def validate(fp: str):
    with open(fp, "r", encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)
    py_compile.compile(fp, doraise=True)

MARKER = "# [MOJIBAKE_FIX_V1]"

# ===========================================================================
# 1. PATCH execution_engine.py
# ===========================================================================
print("=" * 60); print("1. PATCH execution_engine.py"); print("=" * 60)
fp = os.path.join(BASE, "execution_engine.py")
with open(fp, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print(f"  SKIP : marker {MARKER} deja present (idempotent)")
else:
    bak = backup(fp)
    print(f"  backup: {os.path.basename(bak)}")
    new_src, n = apply_moji_fix(src)
    print(f"  {n} sequence(s) mojibake remplacee(s)")

    # Insere le marker en haut du fichier (apres le docstring si present)
    # Cherche la fin du premier docstring de module
    m = re.search(r'^("""[\s\S]*?""")\s*\n', new_src, re.MULTILINE)
    if m:
        insert_at = m.end()
        new_src = new_src[:insert_at] + f"\n{MARKER}\n" + new_src[insert_at:]
    else:
        # Sinon en haut apres encoding
        new_src = f"{MARKER}\n" + new_src

    # Sauvegarde sans BOM
    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    validate(fp)
    print(f"  AST OK + py_compile OK")

# ===========================================================================
# 2. PATCH memo_generator.py (helper defensif sur les snapshots deja en DB)
# ===========================================================================
print("\n" + "=" * 60); print("2. PATCH memo_generator.py - defensive helper"); print("=" * 60)
fp = os.path.join(BASE, "memo_generator.py")
with open(fp, "r", encoding="utf-8-sig") as f:
    src = f.read()

MARKER_MG = "# [MOJIBAKE_FIX_V1_HELPER]"
if MARKER_MG in src:
    print(f"  SKIP : marker {MARKER_MG} deja present")
else:
    bak = backup(fp)
    print(f"  backup: {os.path.basename(bak)}")

    # Construit la fonction helper
    helper_code = (
        f'\n\n{MARKER_MG}\n'
        'def _fix_mojibake(s):\n'
        '    """Tente de reparer un double-encoding UTF-8/cp1252.\n'
        '    Detecte la presence de patterns mojibake et applique le reverse roundtrip.\n'
        '    Si la chaine ne contient pas de mojibake, retourne telle quelle.\n'
        '    """\n'
        '    if not isinstance(s, str) or not s:\n'
        '        return s\n'
        '    # Detection rapide : patterns connus de double-encoding\n'
        '    moji_markers = ("\\u00e2\\u2030\\u00a4", "\\u00e2\\u2020", "\\u00c3\\u00a9", "\\u00c3\\u00a8", "\\u00c3\\u00a0")\n'
        '    if not any(m in s for m in moji_markers):\n'
        '        return s\n'
        '    try:\n'
        '        fixed = s.encode("cp1252", errors="strict").decode("utf-8", errors="strict")\n'
        '        return fixed\n'
        '    except (UnicodeEncodeError, UnicodeDecodeError):\n'
        '        return s\n'
    )

    # Cherche _build_convergence_section pour appliquer le helper sur driver
    # On veut transformer : driver = bucket.get("driver", "")
    # en :                  driver = _fix_mojibake(bucket.get("driver", ""))

    # Recherche du pattern : on cible toutes les occurrences dans _build_convergence_section
    # Strategie : trouver la fonction et patcher les references a "driver"
    func_pattern = r'(def _build_convergence_section\b[\s\S]*?)(?=\ndef\s|\Z)'
    fm = re.search(func_pattern, src)
    if not fm:
        print("  [ERR] _build_convergence_section introuvable")
        sys.exit(1)

    func_body = fm.group(1)
    # Replace tous les .get("driver", ...) par _fix_mojibake(.get("driver", ...))
    # Pattern : <var>.get("driver"[, "default"]) ou ["driver"]
    def wrap_driver_calls(match):
        full = match.group(0)
        # ne pas double-wrap
        # remonter et chercher si _fix_mojibake( est juste avant
        return f'_fix_mojibake({full})'

    new_body = func_body
    # cas 1 : b.get("driver", "")
    new_body = re.sub(
        r'(?<!_fix_mojibake\()\b([a-zA-Z_]\w*)\.get\(\s*["\']driver["\']\s*(?:,\s*[^)]*)?\)',
        lambda m: f'_fix_mojibake({m.group(0)})',
        new_body
    )
    # cas 2 : b["driver"]
    new_body = re.sub(
        r'(?<!_fix_mojibake\()\b([a-zA-Z_]\w*)\[\s*["\']driver["\']\s*\]',
        lambda m: f'_fix_mojibake({m.group(0)})',
        new_body
    )

    n_replacements = func_body.count(".get(") + func_body.count('["driver"]')
    print(f"  Wrap applique sur les references 'driver' dans _build_convergence_section")

    # Remplace dans le src
    new_src = src[:fm.start()] + new_body + src[fm.end():]

    # Insert helper AVANT _build_convergence_section
    target = "def _build_convergence_section"
    idx = new_src.find(target)
    if idx == -1:
        print("  [ERR] insertion impossible")
        sys.exit(1)
    new_src = new_src[:idx] + helper_code + "\n\n" + new_src[idx:]

    with open(fp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    validate(fp)
    print(f"  AST OK + py_compile OK")

# ===========================================================================
# 3. Verification
# ===========================================================================
print("\n" + "=" * 60); print("3. VERIFICATION"); print("=" * 60)
for fp in (os.path.join(BASE, "execution_engine.py"), os.path.join(BASE, "memo_generator.py")):
    with open(fp, "r", encoding="utf-8-sig") as f:
        s = f.read()
    n_moji = sum(s.count(m) for m, _ in MOJI_MAP)
    n_clean = s.count("\u2264") + s.count("\u2192") + s.count("\u2265")
    print(f"  {os.path.basename(fp)} : mojibake restant={n_moji}, clean Unicode={n_clean}")

print("\n[DONE]")
