"""Verifie que shadow_engine.py et shadow_simulate_fills.py acceptent --db."""
import subprocess, sys

for script in ["shadow_engine.py", "shadow_simulate_fills.py"]:
    print(f"\n=== {script} --help ===")
    try:
        r = subprocess.run(
            [sys.executable, script, "--help"],
            capture_output=True, text=True, timeout=10
        )
        print(r.stdout)
        if r.stderr:
            print("STDERR:", r.stderr)
    except Exception as e:
        print(f"EXC: {e}")
