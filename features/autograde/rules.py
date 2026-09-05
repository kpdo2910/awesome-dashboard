"""Grading rules for time-based review.

**No `aqt` in this module** — `tools/test_autograde.py` loads it directly.
"""

AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4

# Seconds. hardMax also draws the question-side bar, so running the bar out
# *is* crossing it.
DEFAULTS = {
    "enabled": False,
    "easyMax": 5,
    "goodMax": 10,
    "hardMax": 15,
}


GLOBAL_KEYS = {
    "enabled": "autoGrade",
    "easyMax": "autoGradeEasyMax",
    "goodMax": "autoGradeGoodMax",
    "hardMax": "autoGradeHardMax",
}

# Grade order used when a card offers fewer than four buttons.
ORDER = (AGAIN, HARD, GOOD, EASY)
ZONES = ("again", "hard", "good", "easy")


def _int(value, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def normalise(settings: dict) -> dict:
    """Clamp and force ascending: a hand-edited config could otherwise make
    whole bands unreachable rather than fail loudly."""
    clean = {"enabled": bool(settings.get("enabled", DEFAULTS["enabled"]))}
    easy = max(1, min(600, _int(settings.get("easyMax"), DEFAULTS["easyMax"])))
    good = max(easy + 1, min(600, _int(settings.get("goodMax"), DEFAULTS["goodMax"])))
    hard = max(good + 1, min(600, _int(settings.get("hardMax"), DEFAULTS["hardMax"])))
    clean.update({"easyMax": easy, "goodMax": good, "hardMax": hard})
    return clean


def global_settings(config: dict) -> dict:

    return normalise(
        {key: config.get(conf_key, DEFAULTS[key])
         for key, conf_key in GLOBAL_KEYS.items()}
    )


def resolve(config: dict, deck_chain) -> dict:
    """Effective settings for a deck, given its ancestors **root first**.

    Merged in turn rather than nearest-wins: an override is partial, so a
    subdeck that only switches the feature on still inherits its parent's
    thresholds.
    """
    settings = global_settings(config)
    overrides = config.get("autoGradeDecks") or {}
    if isinstance(overrides, dict):
        for deck_id in deck_chain:
            entry = overrides.get(str(deck_id))
            if isinstance(entry, dict):
                settings.update(
                    {k: v for k, v in entry.items() if k in DEFAULTS and v is not None}
                )
    return normalise(settings)


def zone_for(elapsed_ms: int, settings: dict) -> str:

    seconds = max(0.0, float(elapsed_ms) / 1000.0)
    if seconds <= settings["easyMax"]:
        return "easy"
    if seconds <= settings["goodMax"]:
        return "good"
    if seconds <= settings["hardMax"]:
        return "hard"
    return "again"


def clamp(wanted: int, eases) -> int:
    """The closest grade a card actually offers, ties going to the kinder one:
    folding a missing Hard down into Again would throw away a real recall."""
    available = sorted({int(e) for e in eases if int(e) in ORDER})
    if not available:
        return AGAIN
    if wanted in available:
        return wanted
    return min(available, key=lambda e: (abs(e - wanted), -e))


def grade(elapsed_ms: int, settings: dict, eases) -> tuple:
    """(ease, zone). `zone` is pre-clamp, for the label."""
    zone = zone_for(elapsed_ms, settings)
    wanted = ORDER[ZONES.index(zone)]
    return clamp(wanted, eases), zone


def failed(eases) -> int:

    return clamp(AGAIN, eases)


def bands(settings: dict) -> list:
    """The bar's three segments as (zone, width) percentages."""
    total = float(settings["hardMax"])
    marks = [
        ("easy", settings["easyMax"]),
        ("good", settings["goodMax"] - settings["easyMax"]),
        ("hard", settings["hardMax"] - settings["goodMax"]),
    ]
    return [(zone, round(span / total * 100, 3)) for zone, span in marks]
