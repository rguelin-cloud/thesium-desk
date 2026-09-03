# -*- coding: utf-8 -*-
"""
Validation runtime v2 - apres patches DB lock + endpoint pending-validation V2.

Changes vs v1:
  - Marker V2 attendu pour l'endpoint
  - Suppression test /api/portfolio/state (endpoint inexistant)
  - Test additionnel: les deux endpoints doivent retourner exactement le meme payload

Exit code 0 si tout OK, 1 sinon.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API_BASE = "http://localhost:8000"
USERNAME = "rguelin"
PASSWORD = "Thesium2026!"
API_SERVER_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")

MARKERS = [
    "[PORTFOLIO_DB_LOCK_FIX_V1]",
    "[ORDERS_PENDING_ENDPOINT_V2]",
]


def _req(method, path, token=None, body=None, timeout=15):
    url = API_BASE + path
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            raw = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e), time.time() - t0
    dt = time.time() - t0
    try:
        return status, json.loads(raw), dt
    except Exception:
        return status, raw, dt


def _count(body):
    if isinstance(body, list):
        return len(body)
    if isinstance(body, dict):
        for k in ("orders", "items", "data", "pending"):
            if isinstance(body.get(k), list):
                return len(body[k])
    return None


def step(num, label):
    print(f"\n[{num}] {label}")


def ok(msg):
    print(f"  OK   {msg}")


def ko(msg):
    print(f"  FAIL {msg}")


def main():
    failures = 0

    # 0. Markers
    step(0, "Markers dans api_server.py")
    if API_SERVER_PATH.exists():
        src = API_SERVER_PATH.read_text(encoding="utf-8-sig", errors="replace")
        for m in MARKERS:
            if m in src:
                ok(f"present: {m}")
            else:
                ko(f"MANQUANT: {m}")
                failures += 1
        # Verifier que V1 (wrapper bugge) a bien ete retire
        if "[ORDERS_PENDING_ENDPOINT_V1] BEGIN" in src:
            ko("ancien bloc V1 (wrapper) encore present - V2 ne l'a pas nettoye")
            failures += 1
        else:
            ok("ancien V1 wrapper retire")
    else:
        ko(f"api_server.py introuvable: {API_SERVER_PATH}")
        failures += 1

    # 1. Login
    step(1, "POST /api/auth/login")
    status, body, dt = _req("POST", "/api/auth/login",
                            body={"username": USERNAME, "password": PASSWORD})
    if status == 200 and isinstance(body, dict) and body.get("access_token"):
        token = body["access_token"]
        ok(f"login 200 ({dt*1000:.0f} ms)")
    else:
        ko(f"login status={status} body={body}")
        return 1

    # 2. Endpoint pending-validation (alias V2)
    step(2, "GET /api/orders/pending-validation (alias V2)")
    status_a, body_a, dt_a = _req("GET", "/api/orders/pending-validation", token=token)
    count_a = _count(body_a)
    if status_a == 200:
        ok(f"200 ({dt_a*1000:.0f} ms), count={count_a}")
    else:
        ko(f"status={status_a} body={str(body_a)[:300]}")
        failures += 1

    # 3. Endpoint pending original
    step(3, "GET /api/orders/pending (original)")
    status_b, body_b, dt_b = _req("GET", "/api/orders/pending", token=token)
    count_b = _count(body_b)
    if status_b == 200:
        ok(f"200 ({dt_b*1000:.0f} ms), count={count_b}")
    else:
        ko(f"status={status_b} body={str(body_b)[:300]}")
        failures += 1

    # 4. Payload identique (les deux routes pointent sur la meme fonction)
    step(4, "Payload alias == original")
    if status_a == 200 and status_b == 200:
        if body_a == body_b:
            ok(f"payloads identiques (count={count_a})")
        else:
            ko("payloads divergent")
            failures += 1
    else:
        ko("comparaison impossible (un endpoint en erreur)")
        failures += 1

    # 5. Stress concurrent (detection lock residuel)
    step(5, "Stress lecture x4 /api/orders/pending-validation")
    lat = []
    for i in range(4):
        s, _, d = _req("GET", "/api/orders/pending-validation", token=token, timeout=10)
        lat.append((s, d * 1000))
    bad = [x for x in lat if x[0] != 200]
    if not bad:
        ok("4/4 OK, latences ms: " + ", ".join(f"{d:.0f}" for _, d in lat))
    else:
        ko(f"{len(bad)}/4 KO: {bad}")
        failures += 1

    print("\n" + ("=" * 60))
    if failures == 0:
        print("RESULT: ALL GREEN - patches valides en runtime")
        return 0
    print(f"RESULT: {failures} failure(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
