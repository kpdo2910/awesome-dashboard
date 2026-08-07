"""Localisation.

Every user-facing string lives in `i18n/<code>.json`, one file per language:

    {
      "name": "English",          # shown in the language picker
      "months": [...],            # 12, short form
      "weekdays": [...],          # 7, Monday first
      "weekdaysShort": [...],     # 7, Monday first
      "thousandsSeparator": ",",
      "strings": { "key": "text", ... }
    }

Adding a language means dropping a new file in that folder — it appears in
Settings automatically, and any key it omits falls back to English.

The language follows Anki's own UI language unless the user picks one here.
Note this only covers the add-on's text: Anki's own screens (its toolbar,
Add, Browse, deck options) follow Anki's language setting, not this one.
"""

import json
import os
import re

from aqt import mw

from . import paths

FALLBACK = "en"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")

_locales: dict = {}
_available: list = []


def _locale_dir() -> str:
    return os.path.join(paths.addon_root(), "i18n")


def _locale(code: str) -> dict:
    if code not in _locales:
        data = {}
        path = os.path.join(_locale_dir(), f"{code}.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"[Awesome Dashboard] cannot load locale {code!r}: {e}")
        _locales[code] = data
    return _locales[code]


def available_languages() -> list:
    """[(code, display name)] for every locale file, English first."""
    global _available
    if _available:
        return _available
    found = []
    try:
        for filename in sorted(os.listdir(_locale_dir())):
            if filename.endswith(".json"):
                code = filename[:-5]
                data = _locale(code)
                if data.get("strings"):
                    found.append((code, str(data.get("name") or code)))
    except OSError as e:
        print(f"[Awesome Dashboard] cannot list locales: {e}")
    found.sort(key=lambda item: (item[0] != FALLBACK, item[1].lower()))
    _available = found
    return found


def current_lang() -> str:
    from . import conf

    codes = {code for code, _ in available_languages()}
    override = conf.get().get("language", "auto")
    if override in codes:
        return override

    lang = ""
    try:
        import anki.lang

        lang = anki.lang.current_lang or ""
    except Exception:
        pass
    if not lang:
        try:
            lang = mw.pm.meta.get("defaultLang", "") or ""
        except Exception:
            lang = ""
    lang = lang.lower().replace("-", "_")
    # Anki reports regional codes like "vi_VN"; match the bare language too.
    for code in sorted(codes, key=len, reverse=True):
        if lang == code or lang.startswith(f"{code}_"):
            return code
    return FALLBACK


def tr(key: str, **params) -> str:
    """A translated string, with any `{name}` placeholders filled in."""
    text = (_locale(current_lang()).get("strings") or {}).get(key)
    if not text:
        text = (_locale(FALLBACK).get("strings") or {}).get(key, key)
    if params:
        text = _PLACEHOLDER.sub(
            lambda m: str(params.get(m.group(1), m.group(0))), text
        )
    return text


def _setting(field: str, default: str) -> str:
    for code in (current_lang(), FALLBACK):
        value = _locale(code).get(field)
        if value:
            return value
    return default


def anki_language_code(code: str) -> str:
    """The Anki language (e.g. "vi_VN") matching one of our locale codes.

    Locales may state it as `ankiLang`; otherwise the first Anki language
    whose code starts with ours is used, so a new locale usually needs no
    extra configuration.
    """
    explicit = _locale(code).get("ankiLang")
    if explicit:
        return str(explicit)
    try:
        import anki.lang

        for _name, anki_code in anki.lang.langs:
            if anki_code == code or anki_code.startswith(f"{code}_"):
                return anki_code
    except Exception:
        pass
    return ""


def date_format() -> str:
    """Template for a full date line, e.g. "{weekday}, {month} {day}"."""
    return _setting("dateFormat", "{weekday}, {month} {day}")


def day_month_format() -> str:
    """Template for a day + month label, used by the heatmap tooltip."""
    return _setting("dayMonth", "{month} {day}")


def date_input_format() -> str:
    """Qt date format for pickers and date labels, e.g. "dd/MM/yyyy"."""
    return _setting("dateInput", "yyyy-MM-dd")


def _from_list(field: str, count: int, index: int) -> str:
    for code in (current_lang(), FALLBACK):
        values = _locale(code).get(field) or []
        if len(values) == count:
            return values[max(0, min(count - 1, index))]
    return ""


def month_name(month_1based: int) -> str:
    return _from_list("months", 12, month_1based - 1)


def weekday_name(weekday_mon0: int) -> str:
    return _from_list("weekdays", 7, weekday_mon0)


def weekday_short(weekday_mon0: int) -> str:
    return _from_list("weekdaysShort", 7, weekday_mon0)


def fmt_int(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    separator = _locale(current_lang()).get("thousandsSeparator", ",")
    return f"{n:,}".replace(",", separator)
