#!/usr/bin/env python3
"""Config-key parity — run from the add-on root:

    python3 tools/check_config.py

A key missing from `config.json` still works, because `conf.get()` merges over
`DEFAULTS`; it just never appears in Anki's config editor. Nothing fails, which
is why this is a check and not a habit.
"""

import ast
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

UNDOCUMENTED_OK = {"debugFakeYears"}


def defaults() -> list:
    """DEFAULTS read with `ast` — importing `core/conf.py` needs `aqt`."""
    tree = ast.parse((ROOT / "core" / "conf.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == "DEFAULTS":
            return [ast.literal_eval(key) for key in node.value.keys]
    return []


def main() -> int:
    keys = defaults()
    if not keys:
        print("PROBLEM  no DEFAULTS dict found in core/conf.py")
        return 1

    shipped = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    documented = set(
        re.findall(r"`([A-Za-z][A-Za-z0-9_]*)`",
                   (ROOT / "config.md").read_text(encoding="utf-8"))
    )

    problems = []

    def verdict(label: str, missing, fix: str) -> None:
        if missing:
            problems.append(label)
            print(f"  PROBLEM  {label}")
            print(f"           - {', '.join(sorted(missing))}")
            print(f"           - {fix}")
        else:
            print(f"  ok       {label}")

    print(f"{len(keys)} key(s) in DEFAULTS\n")
    verdict(
        "every DEFAULTS key ships in config.json",
        set(keys) - set(shipped),
        "add them, or Anki's config editor will never show them",
    )
    verdict(
        "config.json has nothing DEFAULTS has forgotten",
        set(shipped) - set(keys),
        "drop them, or Anki keeps merging a dead key into every profile",
    )
    verdict(
        "every key is documented in config.md",
        set(keys) - documented - UNDOCUMENTED_OK,
        "describe them in config.md, in the section they belong to",
    )

    print("\n" + ("FAILED" if problems else "all good"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
