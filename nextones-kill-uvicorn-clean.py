# -*- coding: utf-8 -*-
"""
nextones-kill-uvicorn-clean.py
Trouve et tue proprement le processus uvicorn ecoutant sur le port 8000.
Ignore Idle/System (PID 0).
"""

import subprocess, sys, time, socket

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

def port_in_use(port=8000):
    """Test connect TCP sur 127.0.0.1:port"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False

def main():
    section("1) Recherche processus LISTENING sur port 8000 via netstat")
    # netstat -ano | findstr :8000 | findstr LISTENING
    r = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True, text=True, encoding="cp850", errors="replace"
    )
    listening_pids = set()
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and ":8000" in parts[1] and parts[3] == "LISTENING":
            pid = parts[-1]
            try:
                pid_int = int(pid)
                if pid_int > 4:  # 0=Idle, 4=System
                    listening_pids.add(pid_int)
                    print(f"  LISTENING : {line.strip()}")
            except ValueError:
                pass
    
    if not listening_pids:
        print("  Aucun processus LISTENING valide sur 8000")
        if port_in_use(8000):
            print("  [WARN] Port 8000 repond pourtant, peut etre un autre check")
        return

    section("2) Detail des processus a tuer")
    for pid in listening_pids:
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "LIST"],
            capture_output=True, text=True, encoding="cp850", errors="replace"
        )
        print(f"\n  PID {pid} :")
        for line in r.stdout.splitlines():
            if line.strip():
                print(f"    {line.strip()}")

    section("3) Kill /F /T (avec arbre des processus enfants)")
    for pid in listening_pids:
        r = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, text=True, encoding="cp850", errors="replace"
        )
        print(f"  PID {pid} : {r.stdout.strip()} {r.stderr.strip()}")

    section("4) Verification post-kill")
    time.sleep(2)
    if port_in_use(8000):
        print("  [KO] Port 8000 toujours occupe")
    else:
        print("  [OK] Port 8000 libre")

    section("PROCHAINES ETAPES")
    print("""
  Lance dans une nouvelle fenetre PowerShell ou en background :
  
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk; py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"
    Start-Sleep -Seconds 6
    $tok = (Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/auth/login" -Body '{"username":"rguelin","password":"Thesium2026!"}' -ContentType "application/json").access_token
    $res = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/universe/scan" -Headers @{Authorization="Bearer $tok"}
    $res | ConvertTo-Json -Depth 5
    py -3.13 .\\nextones-check-reet-status.py
""")

if __name__ == "__main__":
    main()
