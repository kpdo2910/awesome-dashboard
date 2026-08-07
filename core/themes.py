"""Theme palettes: each ships light and dark sets of the same CSS variables.

The default "terracotta" follows the warm-paper design language of the user's
card templates.
"""

THEMES = {
    "terracotta": {
        "light": {
            "bg": "#ece5de",
            "surface": "#ffffff",
            "inset": "#f1ece7",
            "border": "#ece2d9",
            "text": "#211d1a",
            "subtle": "#6b625b",
            "faint": "#a89e96",
            "accent": "#c94f35",
            "accent-soft": "#f7e8e2",
            "accent-hover": "#f2d9cf",
            "shadow": "rgba(70, 45, 30, 0.12)",
            "new": "#c94f35",
            "new-soft": "#f7e8e2",
            "learn": "#a06a2c",
            "learn-soft": "#f5ecdd",
            "due": "#5f7f4e",
            "due-soft": "#e9efe2",
        },
        "dark": {
            "bg": "#1b1715",
            "surface": "#272120",
            "inset": "#332c29",
            "border": "#3a332f",
            "text": "#f2ede9",
            "subtle": "#a79d94",
            "faint": "#8a7d72",
            "accent": "#e5714f",
            "accent-soft": "rgba(229, 113, 79, 0.14)",
            "accent-hover": "rgba(229, 113, 79, 0.26)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#e5714f",
            "new-soft": "rgba(229, 113, 79, 0.16)",
            "learn": "#d9a05b",
            "learn-soft": "rgba(217, 160, 91, 0.16)",
            "due": "#93b478",
            "due-soft": "rgba(147, 180, 120, 0.16)",
        },
    },
    "glass": {
        # Liquid Glass look, Apple system palette — accent #007AFF/#0A84FF,
        # semantic new=blue, learn=orange, due=green, translucent surfaces
        # over a neutral backdrop.
        "light": {
            "bg": "#f2f2f7",
            "surface": "rgba(255, 255, 255, 0.72)",
            "inset": "rgba(120, 120, 128, 0.13)",
            "border": "rgba(60, 60, 67, 0.14)",
            "text": "#1d1d1f",
            "subtle": "rgba(60, 60, 67, 0.62)",
            "faint": "rgba(60, 60, 67, 0.34)",
            "accent": "#007AFF",
            "accent-soft": "rgba(0, 122, 255, 0.12)",
            "accent-hover": "rgba(0, 122, 255, 0.2)",
            "shadow": "rgba(0, 0, 0, 0.1)",
            "new": "#007AFF",
            "new-soft": "rgba(0, 122, 255, 0.12)",
            "learn": "#FF9500",
            "learn-soft": "rgba(255, 149, 0, 0.13)",
            "due": "#28a04c",
            "due-soft": "rgba(52, 199, 89, 0.13)",
            "on-accent": "#ffffff",
        },
        "dark": {
            "bg": "#1c1c1f",
            "surface": "rgba(46, 46, 50, 0.6)",
            "inset": "rgba(120, 120, 128, 0.24)",
            "border": "rgba(255, 255, 255, 0.11)",
            "text": "#f5f5f7",
            "subtle": "rgba(235, 235, 245, 0.62)",
            "faint": "rgba(235, 235, 245, 0.32)",
            "accent": "#0A84FF",
            "accent-soft": "rgba(10, 132, 255, 0.16)",
            "accent-hover": "rgba(10, 132, 255, 0.28)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#0A84FF",
            "new-soft": "rgba(10, 132, 255, 0.16)",
            "learn": "#FF9F0A",
            "learn-soft": "rgba(255, 159, 10, 0.16)",
            "due": "#30D158",
            "due-soft": "rgba(48, 209, 88, 0.16)",
            "on-accent": "#ffffff",
        },
    },
    "matcha": {
        "light": {
            "bg": "#e7eadd",
            "surface": "#ffffff",
            "inset": "#eef0e6",
            "border": "#e0e4d3",
            "text": "#20241b",
            "subtle": "#666d58",
            "faint": "#9aa18c",
            "accent": "#6f8f4e",
            "accent-soft": "#eaf0df",
            "accent-hover": "#dde8cb",
            "shadow": "rgba(50, 60, 35, 0.12)",
            "new": "#6f8f4e",
            "new-soft": "#eaf0df",
            "learn": "#a06a2c",
            "learn-soft": "#f5ecdd",
            "due": "#4e7f8f",
            "due-soft": "#e2edf0",
        },
        "dark": {
            "bg": "#171a13",
            "surface": "#22261d",
            "inset": "#2d3226",
            "border": "#363c2d",
            "text": "#edf0e7",
            "subtle": "#a3ab94",
            "faint": "#7f8771",
            "accent": "#a4c37e",
            "accent-soft": "rgba(164, 195, 126, 0.14)",
            "accent-hover": "rgba(164, 195, 126, 0.26)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#a4c37e",
            "new-soft": "rgba(164, 195, 126, 0.16)",
            "learn": "#d9a05b",
            "learn-soft": "rgba(217, 160, 91, 0.16)",
            "due": "#7eb4c3",
            "due-soft": "rgba(126, 180, 195, 0.16)",
            "on-accent": "#1a1f14",
        },
    },
    "ajisai": {
        "light": {
            "bg": "#e4e7ef",
            "surface": "#ffffff",
            "inset": "#edeff5",
            "border": "#dde1eb",
            "text": "#1d2027",
            "subtle": "#5e6473",
            "faint": "#959cad",
            "accent": "#5a6fb4",
            "accent-soft": "#e7eaf7",
            "accent-hover": "#d8ddf2",
            "shadow": "rgba(40, 50, 90, 0.12)",
            "new": "#5a6fb4",
            "new-soft": "#e7eaf7",
            "learn": "#a06a2c",
            "learn-soft": "#f5ecdd",
            "due": "#5f7f4e",
            "due-soft": "#e9efe2",
        },
        "dark": {
            "bg": "#14161d",
            "surface": "#1f222c",
            "inset": "#2a2e3b",
            "border": "#333849",
            "text": "#e9ecf4",
            "subtle": "#9aa1b5",
            "faint": "#767d92",
            "accent": "#8fa3e3",
            "accent-soft": "rgba(143, 163, 227, 0.14)",
            "accent-hover": "rgba(143, 163, 227, 0.26)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#8fa3e3",
            "new-soft": "rgba(143, 163, 227, 0.16)",
            "learn": "#d9a05b",
            "learn-soft": "rgba(217, 160, 91, 0.16)",
            "due": "#93b478",
            "due-soft": "rgba(147, 180, 120, 0.16)",
            "on-accent": "#14161d",
        },
    },
    "sakura": {
        "light": {
            "bg": "#f0e4e6",
            "surface": "#ffffff",
            "inset": "#f6edee",
            "border": "#eddde0",
            "text": "#251d1f",
            "subtle": "#6f5e62",
            "faint": "#a8969a",
            "accent": "#c25a78",
            "accent-soft": "#f8e7ec",
            "accent-hover": "#f2d6df",
            "shadow": "rgba(90, 40, 55, 0.12)",
            "new": "#c25a78",
            "new-soft": "#f8e7ec",
            "learn": "#a06a2c",
            "learn-soft": "#f5ecdd",
            "due": "#5f7f4e",
            "due-soft": "#e9efe2",
        },
        "dark": {
            "bg": "#1c1517",
            "surface": "#282022",
            "inset": "#342a2d",
            "border": "#3c3134",
            "text": "#f3ecee",
            "subtle": "#ab9a9e",
            "faint": "#87777b",
            "accent": "#e08ba6",
            "accent-soft": "rgba(224, 139, 166, 0.14)",
            "accent-hover": "rgba(224, 139, 166, 0.26)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#e08ba6",
            "new-soft": "rgba(224, 139, 166, 0.16)",
            "learn": "#d9a05b",
            "learn-soft": "rgba(217, 160, 91, 0.16)",
            "due": "#93b478",
            "due-soft": "rgba(147, 180, 120, 0.16)",
            "on-accent": "#1c1517",
        },
    },
    "sumi": {
        "light": {
            "bg": "#eae8e4",
            "surface": "#ffffff",
            "inset": "#f0eeea",
            "border": "#e2dfd9",
            "text": "#1f1e1c",
            "subtle": "#605d58",
            "faint": "#9b9791",
            "accent": "#41403c",
            "accent-soft": "#eceae5",
            "accent-hover": "#e0ddd6",
            "shadow": "rgba(40, 38, 34, 0.12)",
            "new": "#41403c",
            "new-soft": "#eceae5",
            "learn": "#a06a2c",
            "learn-soft": "#f5ecdd",
            "due": "#5f7f4e",
            "due-soft": "#e9efe2",
        },
        "dark": {
            "bg": "#161514",
            "surface": "#211f1e",
            "inset": "#2c2a28",
            "border": "#353230",
            "text": "#efedeb",
            "subtle": "#a5a09a",
            "faint": "#807b75",
            "accent": "#d8d2ca",
            "accent-soft": "rgba(216, 210, 202, 0.12)",
            "accent-hover": "rgba(216, 210, 202, 0.22)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#d8d2ca",
            "new-soft": "rgba(216, 210, 202, 0.14)",
            "learn": "#d9a05b",
            "learn-soft": "rgba(217, 160, 91, 0.16)",
            "due": "#93b478",
            "due-soft": "rgba(147, 180, 120, 0.16)",
            "on-accent": "#211f1e",
        },
    },
}


# Renamed themes keep working for configs saved under the old key.
ALIASES = {"aizome": "glass", "washi": "terracotta"}

# The slots a custom accent may replace. Everything else — backgrounds, text,
# the new/learn/due colours — still comes from the chosen theme.
ACCENT_KEYS = ("accent", "accent-soft", "accent-hover", "on-accent")


def _rgb(value: str):
    value = (value or "").strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    if len(value) != 6:
        return None
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def derive_accents(accent: str) -> dict:
    """The full accent family implied by one colour.

    Soft/hover are the accent at low alpha so they work on light and dark alike;
    on-accent text flips to dark only when the accent is bright enough to need it.
    """
    rgb = _rgb(accent)
    if rgb is None:
        return {}
    r, g, b = rgb
    # Rec. 709 luma: bright accents (yellows, pale tints) need dark text.
    luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    return {
        "accent": "#%02x%02x%02x" % (r, g, b),
        "accent-soft": f"rgba({r}, {g}, {b}, 0.14)",
        "accent-hover": f"rgba({r}, {g}, {b}, 0.24)",
        "on-accent": "#1a1a1a" if luma > 0.62 else "#ffffff",
    }


def custom_accent() -> dict:
    """The user's accent override, or {} when they haven't set one."""
    try:
        from . import conf

        stored = conf.get().get("customAccent")
    except Exception:
        return {}
    if not isinstance(stored, dict):
        return {}
    return {k: v for k, v in stored.items() if k in ACCENT_KEYS and v}


def palette(theme_name: str, night: bool) -> dict:
    theme_name = ALIASES.get(theme_name, theme_name)
    theme = THEMES.get(theme_name) or THEMES["terracotta"]
    pal = dict(theme["dark" if night else "light"])
    pal.setdefault("on-accent", "#ffffff")
    pal.update(custom_accent())
    return pal


def theme_accent(theme_name: str, night: bool = False) -> str:
    """A theme's own accent, ignoring any custom override — for swatches."""
    theme_name = ALIASES.get(theme_name, theme_name)
    theme = THEMES.get(theme_name) or THEMES["terracotta"]
    return theme["dark" if night else "light"]["accent"]


def variables(theme_name: str, night: bool) -> dict:
    """{"--awd-bg": "#…", …} — the palette as CSS custom properties."""
    return {
        f"--awd-{key}": value
        for key, value in palette(theme_name, night).items()
    }


def css_variables(theme_name: str, night: bool) -> str:
    """A <style> block that defines --awd-* variables on :root."""
    lines = "".join(
        f"{key}: {value};" for key, value in variables(theme_name, night).items()
    )
    return f"<style id=\"awd-theme-vars\">:root {{ {lines} }}</style>"
