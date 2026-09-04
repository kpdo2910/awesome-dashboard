#!/usr/bin/env python3
"""Release paperwork check -- run from the add-on root:

    python3 tools/release_check.py                  # validate the release
    python3 tools/release_check.py --base 1.5.0     # ...and require a bump
    python3 tools/release_check.py --print-version  # just the number
    python3 tools/release_check.py --notes          # CHANGELOG body, for a release

One version number has to be spelled the same way in four places: the manifest,
the CHANGELOG heading, and the two link refs at the foot of the CHANGELOG. CI
reads all four through this file so the pull-request gate and the release
workflow can never disagree about what is being released, and so the same check
can be run by hand before pushing.
"""

import argparse
import json
import pathlib
import re
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
HEADING = re.compile(r"^## \[([^\]]+)\](?:\s*-\s*(\S+))?\s*$", re.M)
LINK_REF = re.compile(r"^\[[^\]]+\]:\s+\S+\s*$")


def read_version() -> str:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["human_version"]


def sections(text: str):
    """[(title, date, body)] in file order, with the link-ref block stripped.

    The refs at the foot of the file are not indented and carry no heading, so
    they would otherwise be read as the body of the oldest release.
    """
    found = []
    marks = list(HEADING.finditer(text))
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = "\n".join(
            line for line in text[mark.end():end].splitlines()
            if not LINK_REF.match(line)
        )
        found.append((mark.group(1), mark.group(2), body.strip()))
    return found


def body_of(text: str, title: str):
    for name, _, body in sections(text):
        if name == title:
            return body
    return None


def as_tuple(version: str):
    match = SEMVER.match(version or "")
    return tuple(int(part) for part in match.groups()) if match else None


def check(version: str, base: str | None) -> int:
    text = CHANGELOG.read_text(encoding="utf-8")
    found = sections(text)
    titles = [title for title, _, _ in found]
    problems = []

    print(f"manifest.json says {version}")
    if base:
        print(f"main says {base}")
    print()

    def verdict(label, ok, detail=""):
        print(f"  {'ok' if ok else 'PROBLEM':9}{label}")
        if not ok:
            if detail:
                print(f"           - {detail}")
            problems.append(label)

    verdict(
        "version is X.Y.Z",
        bool(SEMVER.match(version)),
        f"'{version}' cannot be a v-tag or a CHANGELOG heading",
    )

    entry = next((item for item in found if item[0] == version), None)
    verdict(
        f"CHANGELOG has a [{version}] section",
        entry is not None,
        f"rename '## [Unreleased]' to '## [{version}] - {date.today()}' "
        "and add an empty Unreleased above it",
    )

    verdict(
        "[Unreleased] is the first section",
        titles[:1] == ["Unreleased"],
        f"first heading is [{titles[0]}]" if titles else "no sections at all",
    )

    if entry is not None:
        verdict(
            f"[{version}] is the newest release",
            titles[:2] == ["Unreleased", version],
            f"sections start {titles[:3]} -- a new release goes directly "
            "below Unreleased",
        )

        stamp = entry[1]
        valid_date = False
        if stamp:
            try:
                date.fromisoformat(stamp)
                valid_date = True
            except ValueError:
                pass
        verdict(
            "the section is dated YYYY-MM-DD",
            valid_date,
            f"heading reads '## [{version}]{' - ' + stamp if stamp else ''}'",
        )

        verdict(
            "the section says something",
            bool(entry[2]),
            "an empty release note is worse than none -- it ships to the "
            "GitHub release page as-is",
        )

    unreleased = body_of(text, "Unreleased")
    if unreleased is not None:
        verdict(
            "[Unreleased] is empty",
            not unreleased,
            f"{len(unreleased.splitlines())} line(s) still sit there and would "
            f"never appear in a release -- move them under [{version}]",
        )

    tag_ref = re.compile(
        rf"^\[{re.escape(version)}\]:\s+\S+/releases/tag/v{re.escape(version)}\s*$",
        re.M,
    )
    compare_ref = re.compile(
        rf"^\[Unreleased\]:\s+\S+/compare/v{re.escape(version)}\.\.\.HEAD\s*$",
        re.M,
    )
    verdict(
        f"link ref [{version}] points at the tag",
        bool(tag_ref.search(text)),
        f"add: [{version}]: https://github.com/kpdo2910/awesome-dashboard"
        f"/releases/tag/v{version}",
    )
    verdict(
        "link ref [Unreleased] compares against the new tag",
        bool(compare_ref.search(text)),
        "set: [Unreleased]: https://github.com/kpdo2910/awesome-dashboard"
        f"/compare/v{version}...HEAD",
    )

    if base is not None:
        new, old = as_tuple(version), as_tuple(base)
        verdict(
            f"version is above {base}",
            bool(new and old and new > old),
            f"{version} does not follow {base} -- patch for a fix, minor for a "
            "feature, major for a config break",
        )

    print("\n" + ("FAILED" if problems else "all good"))
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", metavar="VERSION",
                        help="version currently on main; require a bump above it")
    parser.add_argument("--print-version", action="store_true",
                        help="print manifest human_version and exit")
    parser.add_argument("--notes", action="store_true",
                        help="print the CHANGELOG body for this version and exit")
    args = parser.parse_args()

    version = read_version()

    if args.print_version:
        print(version)
        return 0

    if args.notes:
        body = body_of(CHANGELOG.read_text(encoding="utf-8"), version)
        if not body:
            print(f"no CHANGELOG section for {version}", file=sys.stderr)
            return 1
        print(body)
        return 0

    return check(version, args.base)


if __name__ == "__main__":
    sys.exit(main())
