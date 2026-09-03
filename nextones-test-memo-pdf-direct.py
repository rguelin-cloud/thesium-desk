# -*- coding: utf-8 -*-
# Teste directement l'endpoint /api/memos/51/pdf et sauve le PDF en local
# pour bypasser cache navigateur
#
# Usage : py -3.13 .\nextones-test-memo-pdf-direct.py
# Sortie : memo-51-v5-direct.pdf dans le dossier courant

import os
import sys
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"
USER = "rguelin"
PWD = "Thesium2026!"
MEMO_ID = 51
OUT = "memo-51-v5-direct.pdf"


def login():
    url = BASE + "/api/auth/login"
    data = json.dumps({"username": USER, "password": PWD}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read())
    token = resp.get("access_token") or resp.get("token")
    if not token:
        print("[ERREUR] login : pas de token dans la reponse")
        print("Reponse : " + str(resp))
        sys.exit(1)
    return token


def fetch_pdf(token):
    url = BASE + "/api/memos/" + str(MEMO_ID) + "/pdf"
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(), r.headers.get("Content-Type", "?"), r.headers.get("Content-Disposition", "?")


def main():
    print("=" * 70)
    print("TEST DIRECT /api/memos/" + str(MEMO_ID) + "/pdf (bypass cache navigateur)")
    print("=" * 70)

    print("Login...")
    try:
        token = login()
        print("Token obtenu (len=" + str(len(token)) + ")")
    except Exception as e:
        print("[ERREUR LOGIN] " + str(e))
        sys.exit(1)

    print("Fetching PDF...")
    try:
        pdf_bytes, ctype, cdisp = fetch_pdf(token)
    except urllib.error.HTTPError as e:
        print("[ERREUR HTTP] " + str(e.code) + " : " + e.reason)
        print("Body : " + str(e.read()[:500]))
        sys.exit(1)
    except Exception as e:
        print("[ERREUR] " + str(e))
        sys.exit(1)

    print("Content-Type : " + ctype)
    print("Content-Disposition : " + cdisp)
    print("Taille PDF : " + str(len(pdf_bytes)) + " bytes")

    out_path = os.path.abspath(OUT)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print("Ecrit : " + out_path)

    # Quick check : PDF version et nombre de pages approx
    head = pdf_bytes[:8].decode("latin-1", errors="replace")
    print("Header : " + repr(head))
    nb_pages = pdf_bytes.count(b"/Type /Page")
    print("Pages approx : " + str(nb_pages))


if __name__ == "__main__":
    main()
