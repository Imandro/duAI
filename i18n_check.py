"""Comprueba que todas las claves usadas con t(...) existen en los JSON.

Uso: python i18n_check.py
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

ROOT = Path(__file__).parent / "duai"
TRANSLATIONS = ROOT / "i18n" / "translations"

PAT = re.compile(r"""\bt\(\s*["']([a-zA-Z0-9_.]+)["']""")
# claves construidas dinamicamente tipo t(f"cli.help_line.{x}") -> se ignoran
PAT_PREFIX = re.compile(r"""\bt\(\s*f["']([a-zA-Z0-9_]+)\.""")

used = {}
for py in sorted(ROOT.rglob("*.py")):
    text = py.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        for key in PAT.findall(line):
            used.setdefault(key, []).append(f"{py.relative_to(ROOT)}:{i}")

tables = {}
for json_file in sorted(TRANSLATIONS.glob("*.json")):
    with open(json_file, encoding="utf-8") as fh:
        tables[json_file.stem] = json.load(fh)


def resolve(table: dict, key: str):
    node = table
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None


missing = {lang: [] for lang in tables}
for key in sorted(used):
    for lang, table in tables.items():
        if resolve(table, key) is None:
            missing[lang].append(key)

total = len(used)
print(f"Claves usadas: {total}")
for lang in sorted(tables):
    miss = missing[lang]
    print(f"  {lang}: faltan {len(miss)}")
    for key in miss:
        print(f"    - {key}   (ej: {used[key][0]}, {len(used[key])} usos)")

# Claves definidas pero sin usar (aviso, no error)
unused = {lang: [] for lang in tables}
for lang, table in tables.items():
    def walk(node, prefix=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{prefix}{k}.")
        elif isinstance(node, str):
            full = prefix[:-1]
            if full not in used:
                unused[lang].append(full)
    walk(table)

for lang in sorted(tables):
    print(f"  {lang}: sin usar {len(unused[lang])}")

# Simetria entre idiomas
if len(tables) == 2:
    langs = sorted(tables)
    a, b = langs

    def flat(node, prefix="", out=None):
        if out is None:
            out = set()
        if isinstance(node, dict):
            for k, v in node.items():
                flat(v, f"{prefix}{k}.", out)
        elif isinstance(node, str):
            out.add(prefix[:-1])
        return out

    fa, fb = flat(tables[a]), flat(tables[b])
    only_a, only_b = sorted(fa - fb), sorted(fb - fa)
    print(f"  claves solo en {a}: {len(only_a)}")
    for k in only_a[:25]:
        print(f"    + {k}")
    print(f"  claves solo en {b}: {len(only_b)}")
    for k in only_b[:25]:
        print(f"    + {k}")

bad = any(missing[lang] for lang in tables)
sys.exit(1 if bad else 0)
