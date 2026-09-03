# -*- coding: utf-8 -*-
"""
Reproduit l'erreur 500 sur POST /api/orders/execute-cycle et capture :
- status code
- response body JSON (avec le 'detail' = str(exception))
- headers
Puis dump les 30 dernieres lignes des logs uvicorn (si trouves).

Lancement :
    py -3.13 .\nextones-trigger-cycle-and-capture-500.py
"""
from __future__ import annotations

import sys
import json
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = "http://127.0.0.1:8000"
USER = "rguelin"
PWD = "Thesium2026!"


def post_json(url: str, payload: dict, token: str | None = None) -> tuple[int, dict | str, dict]:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(raw), dict(r.headers)
            except Exception:
                return r.status, raw, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(raw), dict(e.headers)
        except Exception:
            return e.code, raw, dict(e.headers)


def main() -> int:
    print("=" * 78)
    print("1. Login")
    print("=" * 78)
    code, body, _ = post_json(
        f"{BASE}/api/auth/login", {"username": USER, "password": PWD}
    )
    print(f"  status: {code}")
    if code != 200 or not isinstance(body, dict):
        print(f"  body: {body!r}")
        print("[FATAL] login impossible")
        return 1
    token = body.get("access_token")
    print(f"  token len: {len(token) if token else 0}")
    if not token:
        print("[FATAL] pas de token")
        return 1

    print("\n" + "=" * 78)
    print("2. POST /api/orders/execute-cycle")
    print("=" * 78)
    code, body, hdrs = post_json(f"{BASE}/api/orders/execute-cycle", {}, token=token)
    print(f"  status: {code}")
    print(f"  content-type: {hdrs.get('Content-Type') or hdrs.get('content-type')}")
    print("  body:")
    if isinstance(body, dict):
        print(json.dumps(body, indent=2, ensure_ascii=False))
    else:
        print(body[:4000])

    # Si 500, la cle 'detail' contient str(e) = message exception
    if code == 500 and isinstance(body, dict):
        detail = body.get("detail", "")
        print("\n" + "-" * 78)
        print("EXCEPTION CAPTUREE :")
        print(detail)
        print("-" * 78)

    return 0


if __name__ == "__main__":
    sys.exit(main())
