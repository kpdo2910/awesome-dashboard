"""Filesystem locations, resolved from the add-on root.

Modules live in subpackages now, so `os.path.dirname(__file__)` no longer
points at the add-on folder. Anything that must sit at the root — most
importantly `user_files`, which is the only directory Anki preserves across
add-on updates — goes through here.
"""

import os

ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def addon_root() -> str:
    return ADDON_ROOT


def user_files(*parts: str) -> str:
    """Path inside the add-on's persistent `user_files` directory."""
    path = os.path.join(ADDON_ROOT, "user_files", *parts)
    os.makedirs(path if not os.path.splitext(path)[1] else os.path.dirname(path),
                exist_ok=True)
    return path


def web_asset(*parts: str) -> str:
    return os.path.join(ADDON_ROOT, "web", *parts)
