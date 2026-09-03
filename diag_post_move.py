"""
Compare l'index.html actuel (post-déplacement) avec son backup pour comprendre
ce qui a été corrompu.
"""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
HTML = ROOT / "index.html"

# Trouve le backup le plus récent
backups = sorted(ROOT.glob("index.html.bak_pplx_move_*"), reverse=True)
if not backups:
    print("[ERR] Aucun backup trouvé.")
    raise SystemExit(1)

BAK = backups[0]
print(f"[INFO] Comparaison : {HTML.name} vs {BAK.name}")

cur = HTML.read_text(encoding="utf-8-sig", errors="replace")
bak = BAK.read_text(encoding="utf-8-sig", errors="replace")

def count_all(txt):
    return {
        "<section": len(re.findall(r"<section\b", txt)),
        "</section>": len(re.findall(r"</section>", txt)),
        "<div": len(re.findall(r"<div\b", txt)),
        "</div>": len(re.findall(r"</div>", txt)),
        "<main": len(re.findall(r"<main\b", txt)),
        "</main>": len(re.findall(r"</main>", txt)),
        "<body": len(re.findall(r"<body\b", txt)),
        "</body>": len(re.findall(r"</body>", txt)),
        "<script": len(re.findall(r"<script\b", txt)),
        "</script>": len(re.findall(r"</script>", txt)),
        "<button": len(re.findall(r"<button\b", txt)),
        "</button>": len(re.findall(r"</button>", txt)),
    }

cur_c = count_all(cur)
bak_c = count_all(bak)

print()
print(f"{'TAG':12} {'BACKUP':>8} {'CURRENT':>8} {'DIFF':>6}")
print("-" * 40)
for tag in cur_c:
    diff = cur_c[tag] - bak_c[tag]
    flag = "  <==" if diff != 0 else ""
    print(f"{tag:12} {bak_c[tag]:>8} {cur_c[tag]:>8} {diff:>+6}{flag}")

print()
print("=" * 70)
print("VÉRIF : où est le marker [PPLX_PANEL_MOVED_TO_TODAY] ?")
print("=" * 70)
idx = cur.find("[PPLX_PANEL_MOVED_TO_TODAY]")
if idx >= 0:
    # Trouve la section parente
    # Liste des <section id="tab-...">
    sections = []
    for m in re.finditer(r'<section[^>]*id="(tab-[^"]+)"[^>]*>', cur):
        sections.append((m.start(), m.group(1)))
    parent = None
    for off, name in sections:
        if off < idx:
            parent = name
    print(f"  Marker @ {idx}, parent_section={parent}")

print()
print("=" * 70)
print("CONTEXTE 200 chars AVANT et APRÈS le marker")
print("=" * 70)
if idx >= 0:
    print("--- AVANT ---")
    print(cur[max(0, idx-300):idx])
    print("--- MARKER ---")
    print(cur[idx:idx+100])

# Vérifie où sont les </section> AVANT et APRÈS le marker
print()
print("=" * 70)
print("</section> AVANT le marker (indique fermeture de tab-today)")
print("=" * 70)
closes = [m.start() for m in re.finditer(r"</section>", cur)]
# Trouve le plus proche AVANT et APRÈS
before = [c for c in closes if c < idx]
after  = [c for c in closes if c > idx]
print(f"  Dernier </section> avant marker @ {before[-1] if before else 'NONE'}")
print(f"  1er </section> après marker     @ {after[0] if after else 'NONE'}")
if after:
    print(f"  Contexte 200 char autour du 1er </section> après marker :")
    a = after[0]
    print(cur[max(0,a-100):a+100])
