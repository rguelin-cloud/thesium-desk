# [DIAG_REGEX_RUN_AGENTS_V1] Tester pourquoi la regex echoue
from __future__ import annotations
import re
from pathlib import Path

target = Path(__file__).resolve().parent / "api_server.py"
src = target.read_text(encoding="utf-8-sig")

print("=" * 80)
print("DIAG REGEX run_agents_endpoint")
print("=" * 80)

# 1. Verifier que la chaine existe brute
needle = "def run_agents_endpoint"
print(f"\n1. '{needle}' present en str ? {needle in src}")
idx = src.find(needle)
print(f"   Position : {idx}")
if idx > 0:
    print(f"   Contexte (200 chars) :")
    print(f"   {repr(src[idx:idx+200])}")

# 2. Tester plusieurs regex
print("\n2. Tests regex :")
patterns = [
    r"def\s+run_agents_endpoint",
    r"def\s+run_agents_endpoint\s*\(",
    r"def\s+run_agents_endpoint\s*\([^)]*\)",
    r"def\s+run_agents_endpoint\s*\(([^)]*)\)\s*:\s*\n",
    r"def\s+run_agents_endpoint\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:\s*\n",
    r"def\s+run_agents_endpoint\s*\(([^)]*)\)\s*(?:->\s*[^:]+)?\s*:",
]
for pat in patterns:
    m = re.search(pat, src)
    status = "MATCH" if m else "NO MATCH"
    print(f"   {status:9} : {pat}")
    if m:
        # Afficher le match
        print(f"             -> match.group(0)[:200]={repr(m.group(0)[:200])}")

# 3. Quels caracteres autour de la signature ?
print("\n3. Bytes autour de la signature :")
if idx > 0:
    # Trouver le ':' apres la signature
    end_sig = src.find(":", idx)
    print(f"   ':' a la position {end_sig}")
    print(f"   chars apres ':' (next 50 chars repr):")
    print(f"   {repr(src[end_sig:end_sig+50])}")

# 4. Compter les line endings
print("\n4. Line endings :")
print(f"   \\r\\n count : {src.count(chr(13)+chr(10))}")
print(f"   \\n count   : {src.count(chr(10))}")
print(f"   \\r count   : {src.count(chr(13))}")
