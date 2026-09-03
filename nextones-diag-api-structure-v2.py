# -*- coding: utf-8 -*-
"""[DIAG_API_STRUCTURE_V2]
Verifier que api_server_with_static.py compile bien tel quel (sans patch),
et localiser le pb a la ligne 159.
"""
import sys
import io
import os
import ast
import py_compile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"

with open(API, "r", encoding="utf-8-sig") as f:
    content = f.read()
    lines = content.split("\n")

# Test ast.parse sur le contenu actuel
print("=" * 60)
print("1. Test ast.parse sur le fichier actuel (sans patch)")
print("=" * 60)
try:
    ast.parse(content)
    print("[OK] Le fichier actuel compile")
except SyntaxError as e:
    print(f"[ERR] SyntaxError : {e}")
    print(f"      Ligne : {e.lineno}, offset : {e.offset}")
    print(f"      Text : {e.text!r}")

# Test py_compile
print()
try:
    py_compile.compile(API, doraise=True)
    print("[OK] py_compile passe")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile : {e}")

# Dump lignes 150-170 et 30-60
print("\n" + "=" * 60)
print("2. Lignes 150-170 (contexte autour de l'erreur)")
print("=" * 60)
for i in range(150, 170):
    if i <= len(lines):
        print(f"  L{i}: {lines[i-1]}")

print("\n" + "=" * 60)
print("3. Lignes 30-70 (zone endpoints)")
print("=" * 60)
for i in range(30, 70):
    if i <= len(lines):
        print(f"  L{i}: {lines[i-1]}")

# Cherche tous les imports en haut du fichier
print("\n" + "=" * 60)
print("4. Imports (premieres 35 lignes)")
print("=" * 60)
for i in range(1, 36):
    if i <= len(lines):
        print(f"  L{i}: {lines[i-1]}")
