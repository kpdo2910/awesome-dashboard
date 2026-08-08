"""The user's own background image.

The file is copied into `user_files/`, which is the one directory Anki backs up
and restores around an add-on update (aqt/addons.py `_install`). Keeping only a
path to wherever the user picked it would break the moment they moved the file,
and the add-on folder proper is deleted on every update.

Anki serves add-on files through a regex that is *fullmatch*ed against the path
below the add-on folder, so `__init__.py` exports `user_files/` alongside `web/`
for the image to be reachable at all.
"""

import os
import shutil

from . import conf, paths

# Anki's webview is Chromium, so this is what it can actually decode. SVG is
# left out on purpose: it is a document, and one fetched from disk can carry
# script.
EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")

# One background at a time, stored under a fixed stem. The extension is kept
# because Chromium sniffs content, but a correct one avoids any doubt.
STEM = "background"

MAX_BYTES = 20 * 1024 * 1024


def _existing() -> str:
    """Absolute path of the stored image, or "" when there is none."""
    for extension in EXTENSIONS:
        candidate = paths.user_files(STEM + extension)
        if os.path.exists(candidate):
            return candidate
    return ""


def current() -> str:
    """Filename of the stored image, or "" — this is what the config holds."""
    stored = conf.get().get("backgroundImage") or ""
    if not stored:
        return ""
    # The config can outlive the file: a profile restored without user_files, or
    # a user clearing the folder by hand.
    if not os.path.exists(paths.user_files(str(stored))):
        return ""
    return str(stored)


def check(source: str) -> None:
    """Raise ValueError with a translated reason if `source` is unusable."""
    from .translations import tr

    if os.path.splitext(source)[1].lower() not in EXTENSIONS:
        raise ValueError(tr("bg_bad_type"))
    try:
        if os.path.getsize(source) > MAX_BYTES:
            raise ValueError(tr("bg_too_big"))
    except OSError as e:
        raise ValueError(str(e))


def save(source: str) -> str:
    """Copy `source` in as the background and return its filename.

    Does not touch the config: the caller owns that, so the write lands in the
    same `conf.save` as the rest of the dialog rather than racing it.
    """
    check(source)
    # Drop any previous image first, or a .png would linger behind a new .jpg
    # and `_existing()` would keep finding the stale one.
    remove()
    extension = os.path.splitext(source)[1].lower()
    target = paths.user_files(STEM + extension)
    shutil.copyfile(source, target)
    return os.path.basename(target)


def remove() -> None:
    """Delete the stored image. The config key is the caller's to clear."""
    for extension in EXTENSIONS:
        candidate = paths.user_files(STEM + extension)
        if os.path.exists(candidate):
            try:
                os.remove(candidate)
            except OSError as e:
                print(f"[Awesome Dashboard] could not remove background: {e}")


def css_url(addon_root: str) -> str:
    """`url("…")` for the stored image, or "none" when there is none.

    `addon_root` is the add-on's URL root (`/_addons/<package>`), not its web/
    subfolder — the image lives beside it in user_files/.

    Cache-busted by mtime: the filename is fixed, so replacing the image would
    otherwise keep showing the old one from the webview cache.
    """
    name = current()
    if not name:
        return "none"
    try:
        version = int(os.path.getmtime(paths.user_files(name)))
    except OSError:
        version = 0
    return f'url("{addon_root}/user_files/{name}?v={version}")'
