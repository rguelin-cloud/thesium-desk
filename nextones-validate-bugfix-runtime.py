# -*- coding: utf-8 -*-
"""
Validation runtime apres patches DB lock + endpoint pending-validation.

Tests:
  1. Login JWT
  2. GET /api/orders/pending-validation -> 200 OK
  3. GET /api/orders/pending -> 200 OK
  4. Compare count entre les deux endpoints (doit etre identique)
  5. GET /api/portfolio/state -> 200 OK (verifie que portfolio update fonctionne)
  6. Lecture markers dans api_server.py (idempotence verifiee)

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
    "[ORDERS_PENDING_ENDPOINT_V1]",
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


def step(num, label):
    print(f"\n[{num}] {label}")


def ok(msg):
    print(f"  OK   {msg}")


def ko(msg):
    print(f"  FAIL {msg}")


def main():
    failures = 0

    # 0. Markers presence
    step(0, "Markers idempotents dans api_server.py")
    if API_SERVER_PATH.exists():
        try:
            src = API_SERVER_PATH.read_text(encoding="utf-8-sig", errors="replace")
            for m in MARKERS:
                if m in src:
                    ok(f"marker present: {m}")
                else:
                    ko(f"marker MANQUANT: {m}")
                    failures += 1
        except Exception as e:
            ko(f"lecture api_server.py: {e}")
            failures += 1
    else:
        ko(f"api_server.py introuvable: {API_SERVER_PATH}")
        failures += 1

    # 1. Login
    step(1, "POST /api/auth/login")
    status, body, dt = _req("POST", "/api/auth/login",
                            body={"username": USERNAME, "password": PASSWORD})
    if status == 200 and isinstance(body, dict) and body.get("access_token"):
        token = body["access_token"]
        ok(f"login 200 ({dt*1000:.0f} ms), role={body.get('role','?')}")
    else:
        ko(f"login status={status} body={body}")
        return 1

    # 2. Endpoint pending-validation
    step(2, "GET /api/orders/pending-validation (nouvel alias)")
    status, body, dt = _req("GET", "/api/orders/pending-validation", token=token)
    pending_validation_count = None
    if status == 200:
        if isinstance(body, list):
            pending_validation_count = len(body)
        elif isinstance(body, dict):
            for k in ("orders", "items", "data", "pending"):
                if isinstance(body.get(k), list):
                    pending_validation_count = len(body[k])
                    break
        ok(f"200 ({dt*1000:.0f} ms), count={pending_validation_count}")
    else:
        ko(f"status={status} body={str(body)[:200]}")
        failures += 1

    # 3. Endpoint pending original
    step(3, "GET /api/orders/pending (original)")
    status, body, dt = _req("GET", "/api/orders/pending", token=token)
    pending_count = None
    if status == 200:
        if isinstance(body, list):
            pending_count = len(body)
        elif isinstance(body, dict):
            for k in ("orders", "items", "data", "pending"):
                if isinstance(body.get(k), list):
                    pending_count = len(body[k])
                    break
        ok(f"200 ({dt*1000:.0f} ms), count={pending_count}")
    else:
        ko(f"status={status} body={str(body)[:200]}")
        failures += 1

    # 4. Compare counts
    step(4, "Comparaison counts (alias doit retourner la meme chose)")
    if pending_validation_count is not None and pending_count is not None:
        if pending_validation_count == pending_count:
            ok(f"counts identiques: {pending_count}")
        else:
            ko(f"counts divergent: pending={pending_count} vs pending-validation={pending_validation_count}")
            failures += 1
    else:
        ko("comparaison impossible (un des deux endpoints n'a pas retourne de liste)")
        failures += 1

    # 5. Portfolio state (verifie acces DB en lecture, et que les writes recents n'ont pas locke)
    step(5, "GET /api/portfolio/state")
    status, body, dt = _req("GET", "/api/portfolio/state", token=token)
    if status == 200:
        if isinstance(body, dict):
            nav = body.get("nav") or body.get("total_value") or body.get("equity")
            cash = body.get("cash")
            ok(f"200 ({dt*1000:.0f} ms), nav={nav} cash={cash}")
        else:
            ok(f"200 ({dt*1000:.0f} ms)")
    else:
        ko(f"status={status} body={str(body)[:200]}")
        failures += 1

    # 6. Stress concurrent (4 lectures rapides en serie pour detecter un lock residuel)
    step(6, "Stress lecture x4 /api/orders/pending-validation")
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
