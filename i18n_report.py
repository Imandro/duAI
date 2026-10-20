"""Genera un informe de claves i18n faltantes con sus argumentos de formato.

Uso: python i18n_report.py  ->  imprime i18n_missing.txt
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent / "duai"
TRANSLATIONS = ROOT / "i18n" / "translations"

PAT = re.compile(r"\bt\(\s*[\"']([a-zA-Z0-9_.]+)[\"']([^)]*)\)")


def scan():
    used = defaultdict(list)  # key -> [(file:line, raw_args)]
    for py in sorted(ROOT.rglob("*.py")):
        text = py.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            for m in PAT.finditer(line):
                key, rest = m.group(1), m.group(2)
                kwargs = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=", rest)
                used[key].append((f"{py.relative_to(ROOT)}:{i}", kwargs, line.strip()))
    return used


es = json.load(open(TRANSLATIONS / "es.json", encoding="utf-8"))
en = json.load(open(TRANSLATIONS / "en.json", encoding="utf-8"))


def resolve(table, key):
    node = table
    for part in key.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node if isinstance(node, str) else None


used = scan()
missing = sorted(k for k in used if resolve(es, k) is None or resolve(en, k) is None)

by_ns = defaultdict(list)
for key in missing:
    ns = key.split(".")[0]
    by_ns[ns].append(key)

lines = []
lines.append(f"FALTAN {len(missing)} claves\n")
for ns in sorted(by_ns):
    lines.append(f"\n===== {ns} ({len(by_ns[ns])}) =====")
    for key in by_ns[ns]:
        sites = used[key]
        kw = sorted({k for _, args, _ in sites for k in args})
        lines.append(f"\n{key}   kwargs={kw}")
        lines.append(f"   {sites[0][2][:150]}")
        if len(sites) > 1:
            lines.append(f"   (x{len(sites)} sitios)")

out = Path(__file__).parent / "i18n_missing.txt"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"i18n_missing.txt: {len(missing)} claves faltantes")
for ns in sorted(by_ns):
    print(f"  {ns}: {len(by_ns[ns])}")
