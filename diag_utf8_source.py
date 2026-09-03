# diag_utf8_source.py
# Trouver la ligne de code qui ecrit "Ordre net emis" avec double encoding
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

root = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

print("=" * 70)
print("1. Fichiers contenant 'Ordre net emis' (clean) ou mojibake")
print("=" * 70)
patterns = [
    ("emis_clean", "Ordre net émis"),
    ("emis_mojibake_simple", "Ordre net Ã©mis"),
    ("emis_mojibake_double", "Ordre net Ã\u0083Â©mis"),  # Ã©mis double-encoded
    ("deja_clean", "déjà"),
    ("deja_mojibake", "dÃ©jÃ"),
]

for py_file in root.rglob("*.py"):
    if "_backups" in str(py_file) or "node_modules" in str(py_file):
        continue
    try:
        # Lire en UTF-8 strict
        content = py_file.read_text(encoding="utf-8-sig", errors="strict")
        for name, pat in patterns:
            if pat in content:
                rel = py_file.relative_to(root)
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if pat in line:
                        print(f"  {rel} L{i+1} ({name}): {line.strip()[:130]}")
    except UnicodeDecodeError as e:
        rel = py_file.relative_to(root)
        # Tenter latin-1
        try:
            content = py_file.read_text(encoding="latin-1")
            for name, pat in patterns:
                if pat in content:
                    print(f"  [LATIN1] {rel} contient '{name}'")
        except Exception:
            print(f"  [READ_ERR] {rel}: {e}")
    except Exception as e:
        pass

print()
print("=" * 70)
print("2. Bytes raw de la chaine 'Ordre net emis' dans execution_engine.py")
print("=" * 70)
ee = root / "execution_engine.py"
if ee.exists():
    raw = ee.read_bytes()
    # Chercher pattern bytes
    targets = {
        b"Ordre net \xc3\xa9mis": "UTF-8 propre (1 'e' avec 2 bytes c3 a9)",
        b"Ordre net \xc3\x83\xc2\xa9mis": "UTF-8 double-encoded (4 bytes c3 83 c2 a9)",
        b"Ordre net \xe9mis": "Latin-1 (1 byte e9)",
    }
    for needle, desc in targets.items():
        if needle in raw:
            idx = raw.index(needle)
            # Position en ligne
            line_no = raw[:idx].count(b"\n") + 1
            print(f"  Trouve: {desc}  L{line_no}")
            ctx_start = max(0, idx - 40)
            ctx_end = min(len(raw), idx + 60)
            print(f"  Context bytes: {raw[ctx_start:ctx_end]}")
            print()

print()
print("=" * 70)
print("3. index.html - premieres 500 chars + bytes")
print("=" * 70)
idx_html = root / "index.html"
if idx_html.exists():
    raw = idx_html.read_bytes()
    print(f"  Taille : {len(raw)} bytes")
    print(f"  BOM ? {raw[:3] == b'\\xef\\xbb\\xbf'}")
    print(f"  Premiers 200 bytes : {raw[:200]}")
    print()
    # Chercher <head>
    head_idx = raw.find(b"<head>")
    if head_idx > -1:
        print(f"  <head> trouve a offset {head_idx}")
        print(f"  Apres head (300 bytes) : {raw[head_idx:head_idx+300]}")
    else:
        print(f"  Pas de <head> trouve")
    # Chercher charset
    if b"charset" in raw[:2000]:
        idx = raw.find(b"charset")
        print(f"  charset trouve a offset {idx}: {raw[idx-30:idx+50]}")
    else:
        print(f"  PAS DE charset declare en debut de fichier !")
