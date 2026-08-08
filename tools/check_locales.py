#!/usr/bin/env python3
"""Locale health check — run from the add-on root:

    python3 tools/check_locales.py

Reports per-locale keys missing against English, tr() keys no locale defines,
and strings nothing references. Exits non-zero so it can gate a release.
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FALLBACK = "en"
META_FIELDS = {"months": 12, "weekdays": 7, "weekdaysShort": 7}
# Keys built at runtime as tr(f"prefix_{value}").
DYNAMIC_PREFIXES = ("theme_", "appearance_", "greeting_", "color_", "ob_feat_")


def load_locales() -> dict:
    locales = {}
    for path in sorted((ROOT / "i18n").glob("*.json")):
        locales[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return locales


def used_keys() -> set:
    keys = set()
    pattern = re.compile(r"""\btr\(\s*["']([A-Za-z0-9_]+)["']""")
    for path in ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or path.parts[-2:-1] == ("tools",):
            continue
        keys |= set(pattern.findall(path.read_text(encoding="utf-8")))
    return keys


def main() -> int:
    locales = load_locales()
    if FALLBACK not in locales:
        print(f"error: no {FALLBACK}.json")
        return 1

    problems = 0
    reference = set(locales[FALLBACK]["strings"])
    print(f"{len(locales)} locale(s): {', '.join(sorted(locales))}")
    print(f"{len(reference)} strings in {FALLBACK}\n")

    for code, data in sorted(locales.items()):
        issues = []
        strings = set(data.get("strings") or {})
        missing = reference - strings
        extra = strings - reference
        if missing:
            issues.append(f"missing {len(missing)}: {sorted(missing)[:8]}")
        if extra:
            issues.append(f"not in {FALLBACK} {len(extra)}: {sorted(extra)[:8]}")
        for field, count in META_FIELDS.items():
            values = data.get(field) or []
            if len(values) != count:
                issues.append(f"{field} has {len(values)}, expected {count}")
        if not data.get("name"):
            issues.append("no display name")
        status = "ok" if not issues else "PROBLEM"
        print(f"  {code:6} {data.get('name', '?'):14} {status}")
        for issue in issues:
            print(f"         - {issue}")
        problems += len(issues)

    used = used_keys()
    undefined = sorted(
        key for key in used
        if key not in reference and not key.startswith(DYNAMIC_PREFIXES)
    )
    unused = sorted(
        key for key in reference
        if key not in used and not key.startswith(DYNAMIC_PREFIXES)
    )
    print(f"\ntr() keys with no string: {undefined or 'none'}")
    if undefined:
        problems += len(undefined)
    print(f"strings never referenced: {len(unused)}")
    if unused:
        print(f"  {unused}")

    print("\n" + ("FAILED" if problems else "all good"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
