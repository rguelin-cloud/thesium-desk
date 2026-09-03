"""Diag : trouver OU le cycle prod se termine pour brancher shadow_hook."""
import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Lister les .py qui contiennent run_decision_cycle / execute_cycle
patterns = [r"run_decision_cycle", r"execute_cycle", r"def\s+run_cycle"]

print("=== FICHIERS contenant declencheurs cycle ===")
for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(ROOT, fname)
    if os.path.isdir(fpath):
        continue
    try:
        with open(fpath, "rb") as f:
            data = f.read().decode("utf-8-sig", errors="replace")
    except Exception:
        continue
    matches = []
    for pat in patterns:
        for m in re.finditer(pat, data):
            line_no = data[:m.start()].count("\n") + 1
            matches.append((line_no, pat))
    if matches:
        print(f"\n--- {fname} ({len(matches)} matches) ---")
        for ln, pat in matches[:5]:
            line = data.split("\n")[ln-1].strip()[:120]
            print(f"  L{ln}: [{pat}] {line}")

# Chercher specifiquement la def execute_cycle / run_decision_cycle
print("\n\n=== DEFINITIONS execute_cycle / run_decision_cycle ===")
for fname in sorted(os.listdir(ROOT)):
    if not fname.endswith(".py"):
        continue
    fpath = os.path.join(ROOT, fname)
    if os.path.isdir(fpath):
        continue
    try:
        with open(fpath, "rb") as f:
            data = f.read().decode("utf-8-sig", errors="replace")
    except Exception:
        continue
    for m in re.finditer(r"^(async\s+def|def)\s+(execute_cycle|run_decision_cycle)\b", data, re.M):
        line_no = data[:m.start()].count("\n") + 1
        line = data.split("\n")[line_no-1].strip()[:120]
        print(f"  {fname}:L{line_no}: {line}")

# Chercher returns dans execute_cycle (= point d'insertion hook)
print("\n\n=== RETURNS dans execute_cycle (point d'integration hook) ===")
target_file = os.path.join(ROOT, "scheduler.py")
if not os.path.exists(target_file):
    # Chercher tout fichier contenant def execute_cycle
    for fname in sorted(os.listdir(ROOT)):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(ROOT, fname)
        try:
            with open(fpath, "rb") as f:
                data = f.read().decode("utf-8-sig", errors="replace")
        except Exception:
            continue
        if re.search(r"^(async\s+def|def)\s+execute_cycle\b", data, re.M):
            target_file = fpath
            print(f"  -> target_file = {fname}")
            break

print(f"\n  scanning {os.path.basename(target_file)}...")
if os.path.exists(target_file):
    with open(target_file, "rb") as f:
        data = f.read().decode("utf-8-sig", errors="replace")
    lines = data.split("\n")
    in_func = False
    indent = 0
    for i, ln in enumerate(lines, 1):
        if re.match(r"^(async\s+def|def)\s+execute_cycle\b", ln):
            in_func = True
            indent = len(ln) - len(ln.lstrip())
            print(f"  L{i}: [DEF] {ln.strip()[:120]}")
            continue
        if in_func:
            cur_indent = len(ln) - len(ln.lstrip()) if ln.strip() else None
            if cur_indent is not None and cur_indent <= indent and ln.strip():
                in_func = False
                continue
            if "return" in ln and re.search(r"\breturn\b", ln):
                print(f"  L{i}: [RET] {ln.strip()[:120]}")
            if re.search(r"cycle_id\s*=", ln):
                print(f"  L{i}: [CID] {ln.strip()[:120]}")
