"""Inspecte la signature exacte de pplx_query() et regarde comment
   pplx_thesis_agent l'appelle (référence qui marche)."""
import inspect, re, sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
sys.path.insert(0, str(ROOT))

print("=" * 70)
print("1) SIGNATURE DE pplx_query")
print("=" * 70)
from pplx_client import pplx_query, MODEL_FAST, MODEL_DEEP, MODEL_REASON  # noqa
sig = inspect.signature(pplx_query)
print(f"  pplx_query{sig}")
print(f"  Doc: {pplx_query.__doc__}")
print()
print("  Source de pplx_query :")
src = inspect.getsource(pplx_query)
print(src[:3000])

print()
print("=" * 70)
print("2) COMMENT pplx_thesis_agent.py APPELLE pplx_query")
print("=" * 70)
ta = (ROOT / "pplx_thesis_agent.py").read_text(encoding="utf-8-sig", errors="replace")
# Trouve les appels
for m in re.finditer(r"pplx_query\s*\([^)]*\)", ta, re.DOTALL):
    print(f"  {m.group(0)[:400]}")
    print()

# Affiche aussi la définition du schema utilisé
print()
print("=" * 70)
print("3) SCHEMAS définis dans pplx_thesis_agent.py")
print("=" * 70)
for m in re.finditer(r"(_SCHEMA\w*|schema)\s*=\s*\{[^}]*\}", ta, re.DOTALL):
    print(f"  {m.group(0)[:600]}")
    print()

print()
print("=" * 70)
print("4) COMMENT pplx_crypto_agent et pplx_factor_agent APPELLENT pplx_query")
print("=" * 70)
for fn in ["pplx_crypto_agent.py", "pplx_factor_agent.py"]:
    p = ROOT / fn
    if not p.exists():
        continue
    print(f"\n--- {fn} ---")
    txt = p.read_text(encoding="utf-8-sig", errors="replace")
    for m in re.finditer(r"pplx_query\s*\([^)]*\)", txt, re.DOTALL):
        print(f"  {m.group(0)[:400]}")
