"""Resolve every $ref in bus-eta-openapi.yaml and report unresolved ones."""
import re
import sys

import yaml

path = sys.argv[1] if len(sys.argv) > 1 else "bus-eta-openapi.yaml"
doc = yaml.safe_load(open(path))

refs = set()


def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "$ref" and isinstance(v, str):
                refs.add(v)
            else:
                walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)


walk(doc)

defs = {}  # section -> set(names)
for section in ("schemas", "parameters", "examples", "responses", "requestBodies"):
    defs[section] = set(doc.get("components", {}).get(section, {}).keys())


def _is_resolved(ref: str) -> bool:
    parts = ref.split("/")
    if len(parts) >= 4 and parts[0] == "#" and parts[1] == "components":
        section, name = parts[2], parts[3]
        return name in defs.get(section, set())
    return False


unresolved = [r for r in refs if not _is_resolved(r)]

print(f"total $ref mentions: {len(refs)}")
print(f"schemas defined: {len(defs)}")
print(f"unresolved: {len(unresolved)}")
for r in sorted(refs)[:15]:
    print("  ", r)
if unresolved:
    print("UNRESOLVED:", unresolved)
    sys.exit(1)
print("OK: all $refs resolve")
