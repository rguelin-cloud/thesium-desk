"""Identifie le fichier CSS du thème et extrait les variables/règles utilisées."""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
html = (ROOT / "index.html").read_text(encoding="utf-8-sig", errors="replace")

# 1) Liens vers fichiers CSS dans le HTML
print("=" * 70)
print("1) <link rel='stylesheet' href='...'> dans index.html")
print("=" * 70)
for m in re.finditer(r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*>', html):
    print(f"  {m.group(0)}")
print()
print("2) <style> inline dans index.html (tailles)")
print("=" * 70)
for i, m in enumerate(re.finditer(r'<style[^>]*>(.*?)</style>', html, re.DOTALL)):
    print(f"  Bloc <style> #{i+1}: {len(m.group(1))} chars")

# 3) Fichiers .css dans le workspace
print()
print("=" * 70)
print("3) FICHIERS .css DANS LE PROJET")
print("=" * 70)
for css in ROOT.rglob("*.css"):
    if "_backups" in str(css) or "node_modules" in str(css):
        continue
    try:
        size = css.stat().st_size
        print(f"  {css.relative_to(ROOT)}  ({size:,} bytes)")
    except:
        pass

# 4) Pour chaque CSS principal (pas dans backups), extrait les vars + règles dark
print()
print("=" * 70)
print("4) ANALYSE DES CSS — variables et règles [data-theme='dark']")
print("=" * 70)
for css in ROOT.rglob("*.css"):
    if "_backups" in str(css) or "node_modules" in str(css):
        continue
    try:
        txt = css.read_text(encoding="utf-8-sig", errors="replace")
    except:
        continue
    
    print(f"\n--- {css.name} ({css.stat().st_size:,} bytes) ---")
    
    # Variables CSS
    var_defs = list(re.finditer(r'(--[a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*([^;]+);', txt))
    seen = {}
    for m in var_defs:
        seen[m.group(1)] = seen.get(m.group(1), [])
        seen[m.group(1)].append(m.group(2).strip())
    
    if seen:
        print(f"  Variables CSS ({len(seen)} uniques) :")
        for name, vals in sorted(seen.items()):
            uniq = list(dict.fromkeys(vals))
            print(f"    {name:30} = {uniq}")
    
    # Sélecteur :root, [data-theme="light"], [data-theme="dark"]
    print("\n  Sélecteurs de thème :")
    for pat, label in [
        (r':root\s*\{[^}]+\}', ':root'),
        (r'\[data-theme=["\']light["\']\]\s*\{[^}]+\}', 'data-theme=light'),
        (r'\[data-theme=["\']dark["\']\]\s*\{[^}]+\}', 'data-theme=dark'),
    ]:
        for m in re.finditer(pat, txt, re.DOTALL):
            body = m.group(0)
            print(f"    [{label}] {body[:600].strip()}")
            print()
    
    # Règle .card
    print("\n  Règles .card / .tab-content :")
    for pat in [r'\.card\s*\{[^}]+\}', r'\.tab-content\b[^{]*\{[^}]+\}', r'\.table-section\s*\{[^}]+\}']:
        for m in re.finditer(pat, txt, re.DOTALL):
            print(f"    {m.group(0)[:300].strip()}")
            print()
