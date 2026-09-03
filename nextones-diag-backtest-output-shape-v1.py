"""
Diag : appelle le backtest existant pour voir la structure exacte du JSON output.
Necessite API running sur 8000. Login admin.
ASCII pur.
"""
import json, sys, urllib.request, urllib.parse, urllib.error

API = "http://127.0.0.1:8000"
USER = "rguelin"
PWD = "Thesium2026!"

def post(path, body, token=None):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

def get(path, token=None):
    req = urllib.request.Request(API + path, method="GET")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))

print("=" * 70)
print("DIAG BACKTEST OUTPUT SHAPE")
print("=" * 70)

# Login
try:
    auth = post("/api/auth/login", {"username": USER, "password": PWD})
    token = auth.get("access_token") or auth.get("token")
    print(f"[1] Login OK, token len={len(token) if token else 0}")
except Exception as e:
    print(f"[1] LOGIN FAIL: {e}")
    sys.exit(1)

# Variantes plausibles d'endpoint backtest
endpoints_post = [
    "/api/backtest/run",
    "/api/backtest",
    "/api/run-backtest",
]
endpoints_get = [
    "/api/backtest/presets",
    "/api/backtest/config",
]

body = {"preset": "equity_only", "period_months": 12, "capital": 100000, "benchmark": "SPY"}
print("\n[2] Tentatives POST avec body:", json.dumps(body))
for ep in endpoints_post:
    try:
        r = post(ep, body, token)
        print(f"  {ep} -> OK")
        # Structure top-level
        if isinstance(r, dict):
            print(f"    keys: {list(r.keys())[:30]}")
            # snapshot des sous-cles equity / metrics
            for k in ("equity_curve", "metrics", "benchmark_curve", "trades", "summary", "config"):
                if k in r:
                    v = r[k]
                    if isinstance(v, list):
                        print(f"    {k}: list len={len(v)}", "sample[0]=", str(v[0])[:120] if v else "(empty)")
                    elif isinstance(v, dict):
                        print(f"    {k}: dict keys={list(v.keys())[:20]}")
                    else:
                        print(f"    {k}: {str(v)[:120]}")
        else:
            print(f"    type={type(r).__name__}, preview={str(r)[:300]}")
        break
    except urllib.error.HTTPError as e:
        print(f"  {ep} -> HTTP {e.code} {e.reason}")
    except Exception as e:
        print(f"  {ep} -> ERR {e}")

print("\n[3] GET endpoints (presets/config)")
for ep in endpoints_get:
    try:
        r = get(ep, token)
        print(f"  {ep} -> OK keys={list(r.keys()) if isinstance(r, dict) else type(r).__name__}")
    except urllib.error.HTTPError as e:
        print(f"  {ep} -> HTTP {e.code}")
    except Exception as e:
        print(f"  {ep} -> ERR {e}")

print("\nDONE")
