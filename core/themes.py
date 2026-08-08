"""Theme palettes: each ships light and dark sets of the same CSS variables.

The "terracotta" palette follows the warm-paper design language of the user's
card templates.

A theme may add "accent-grad", a CSS gradient painted on large accent surfaces
(buttons, pills, progress bars). "accent" stays a solid colour regardless: it is
what text, borders, SVG fills and the whole Qt side are drawn with, none of which
accept a gradient. See `palette()` for why the key is always emitted.
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
    "aurora": {
        # Violet to cyan. "accent" is the midpoint of the two stops, so text and
        # borders read as part of the same colour rather than as one end of it.
        "light": {
            "bg": "#eceef6",
            "surface": "#ffffff",
            "inset": "#f2f4fa",
            "border": "#e0e4f0",
            "text": "#1b1e28",
            "subtle": "#5d6474",
            "faint": "#959cae",
            "accent": "#4078d4",
            "accent-grad": "linear-gradient(135deg, #6247e5 0%, #1fa9c4 100%)",
            "accent-soft": "rgba(64, 120, 212, 0.13)",
            "accent-hover": "rgba(64, 120, 212, 0.22)",
            "shadow": "rgba(35, 45, 85, 0.12)",
            "new": "#4078d4",
            "new-soft": "rgba(64, 120, 212, 0.13)",
            "learn": "#a06a2c",
            "learn-soft": "#f5ecdd",
            "due": "#1f9aa8",
            "due-soft": "rgba(31, 154, 168, 0.14)",
            "on-accent": "#ffffff",
        },
        "dark": {
            "bg": "#14161f",
            "surface": "#1f2230",
            "inset": "#2a2e3e",
            "border": "#33384b",
            "text": "#e9ecf6",
            "subtle": "#9aa1b7",
            "faint": "#767d94",
            "accent": "#64abf5",
            "accent-grad": "linear-gradient(135deg, #8a7bff 0%, #3edceb 100%)",
            "accent-soft": "rgba(100, 171, 245, 0.15)",
            "accent-hover": "rgba(100, 171, 245, 0.26)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#64abf5",
            "new-soft": "rgba(100, 171, 245, 0.16)",
            "learn": "#d9a05b",
            "learn-soft": "rgba(217, 160, 91, 0.16)",
            "due": "#3edceb",
            "due-soft": "rgba(62, 220, 235, 0.16)",
            "on-accent": "#14161f",
        },
    },
    "sunset": {
        "light": {
            "bg": "#f4eae6",
            "surface": "#ffffff",
            "inset": "#faf1ee",
            "border": "#f0e0da",
            "text": "#261c1a",
            "subtle": "#6f5d58",
            "faint": "#a89690",
            "accent": "#e44c5b",
            "accent-grad": "linear-gradient(135deg, #f2643c 0%, #d6357a 100%)",
            "accent-soft": "rgba(228, 76, 91, 0.13)",
            "accent-hover": "rgba(228, 76, 91, 0.22)",
            "shadow": "rgba(95, 45, 35, 0.13)",
            "new": "#e44c5b",
            "new-soft": "rgba(228, 76, 91, 0.13)",
            "learn": "#d18327",
            "learn-soft": "rgba(209, 131, 39, 0.15)",
            "due": "#a34a86",
            "due-soft": "rgba(163, 74, 134, 0.14)",
            "on-accent": "#ffffff",
        },
        "dark": {
            "bg": "#1c1416",
            "surface": "#281e21",
            "inset": "#34282b",
            "border": "#3d2f33",
            "text": "#f5ebe9",
            "subtle": "#ac9995",
            "faint": "#88746f",
            "accent": "#f87371",
            "accent-grad": "linear-gradient(135deg, #ff9153 0%, #f2568f 100%)",
            "accent-soft": "rgba(248, 115, 113, 0.15)",
            "accent-hover": "rgba(248, 115, 113, 0.26)",
            "shadow": "rgba(0, 0, 0, 0.5)",
            "new": "#f87371",
            "new-soft": "rgba(248, 115, 113, 0.16)",
            "learn": "#ff9153",
            "learn-soft": "rgba(255, 145, 83, 0.16)",
            "due": "#f2568f",
            "due-soft": "rgba(242, 86, 143, 0.16)",
            "on-accent": "#1c1416",
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
}


# Renamed and retired themes keep working for configs saved under the old key.
# Ajisai was the blue one, so it lands on Aurora; Sumi was neutral ink, and the
# nearest remaining neutral is Glass.
ALIASES = {
    "aizome": "glass",
    "washi": "terracotta",
    "ajisai": "aurora",
    "sumi": "glass",
}

# The slots a custom accent may replace. Everything else — backgrounds, text,
# the new/learn/due colours — still comes from the chosen theme.
ACCENT_KEYS = ("accent", "accent-grad", "accent-soft", "accent-hover", "on-accent")

# Default gradient angle, in CSS degrees (0 = upward, 90 = rightward).
GRADIENT_ANGLE = 135

# How far the page background is pulled toward each accent stop's hue. It can be
# this strong only because `tint()` keeps the background's own lightness — mixing
# the raw stop in at even 0.16 cost Aurora's dark mode 3 points of text contrast.
PAGE_TINT = 0.5


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


def gradient_css(start: str, end: str, angle: int = GRADIENT_ANGLE) -> str:
    return f"linear-gradient({int(angle)}deg, {start} 0%, {end} 100%)"


def parse_gradient(value: str):
    """(start, end, angle) out of a gradient string, or None if it isn't one."""
    if not isinstance(value, str) or not value.strip().startswith("linear-gradient"):
        return None
    inner = value[value.index("(") + 1:value.rindex(")")]
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) < 3:
        return None
    try:
        angle = int(float(parts[0].replace("deg", "").strip()))
    except ValueError:
        angle = GRADIENT_ANGLE
    stops = [p.split()[0] for p in parts[1:] if p.split()]
    if len(stops) < 2:
        return None
    return stops[0], stops[-1], angle


def shift_hue(color: str, degrees: int) -> str:
    """Rotate a colour's hue, keeping its lightness and saturation.

    Used for the second stop when a solid theme is first turned into a gradient:
    a hue neighbour blends smoothly, where an arbitrary colour rarely does.
    """
    import colorsys

    rgb = _rgb(color)
    if rgb is None:
        return color
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in rgb))
    r, g, b = colorsys.hls_to_rgb((h + degrees / 360.0) % 1.0, l, s)
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


def blend(base: str, tint: str, ratio: float) -> str:
    """`base` with `ratio` of `tint` mixed into it."""
    a, b = _rgb(base), _rgb(tint)
    if a is None or b is None:
        return base
    return "#%02x%02x%02x" % tuple(
        round(a[i] * (1 - ratio) + b[i] * ratio) for i in range(3)
    )


def tint(base: str, toward: str, ratio: float) -> str:
    """`base` pulled toward `toward`'s hue, keeping `base`'s own lightness.

    Blending a colour in raw also drags the brightness with it, which is fatal
    behind text: a bright dark-mode accent mixed into a dark page lightens it
    until the body copy stops being readable. Taking only the hue and saturation
    shifts the colour without moving the contrast ratio.
    """
    import colorsys

    a, b = _rgb(base), _rgb(toward)
    if a is None or b is None:
        return base
    lightness = colorsys.rgb_to_hls(*(c / 255 for c in a))[1]
    hue, _, saturation = colorsys.rgb_to_hls(*(c / 255 for c in b))
    shifted = colorsys.hls_to_rgb(hue, lightness, saturation)
    return blend(base, "#%02x%02x%02x" % tuple(round(c * 255) for c in shifted), ratio)


def mix(first: str, second: str) -> str:
    """The midpoint of two colours — the solid stand-in for a gradient."""
    a, b = _rgb(first), _rgb(second)
    if a is None or b is None:
        return first or second or "#000000"
    return "#%02x%02x%02x" % tuple((a[i] + b[i]) // 2 for i in range(3))


def derive_gradient(start: str, end: str, angle: int = GRADIENT_ANGLE) -> dict:
    """The accent family for a two-stop gradient.

    Everything except the gradient itself is derived from the midpoint, so the
    solid slots (text on links, tints, the heatmap) sit in the middle of the
    gradient instead of matching one end and clashing with the other.
    """
    family = derive_accents(mix(start, end))
    if not family:
        return {}
    family["accent-grad"] = gradient_css(start, end, angle)
    return family


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
    theme = THEMES.get(theme_name) or THEMES["glass"]
    pal = dict(theme["dark" if night else "light"])
    pal.setdefault("on-accent", "#ffffff")

    override = custom_accent()
    if override:
        # A custom accent replaces the whole family. Dropping the theme's own
        # gradient first stops a solid override from leaving the old gradient
        # painted on every button.
        pal.pop("accent-grad", None)
        pal.update(override)

    # Always emit the key, using the solid accent when there is no gradient: a
    # plain colour is a valid `background` value, so CSS needs no fallback, and
    # AwdTheme.apply cannot leave a stale gradient behind when the next theme
    # has none of its own.
    pal.setdefault("accent-grad", pal["accent"])
    pal["bg-grad"] = _page_gradient(pal)
    return pal


def _page_gradient(pal: dict) -> str:
    """The page background, tinted by the accent gradient when there is one.

    Follows the same always-emit rule as `accent-grad`, and falls back to the
    flat `bg`. This sits behind every word on the screen, so it shifts hue only
    — see `tint()`.
    """
    parsed = parse_gradient(pal.get("accent-grad", ""))
    if not parsed:
        return pal["bg"]
    start, end, angle = parsed
    return gradient_css(
        tint(pal["bg"], start, PAGE_TINT), tint(pal["bg"], end, PAGE_TINT), angle
    )


def theme_accent(theme_name: str, night: bool = False) -> str:
    """A theme's own accent, ignoring any custom override — for swatches."""
    theme_name = ALIASES.get(theme_name, theme_name)
    theme = THEMES.get(theme_name) or THEMES["glass"]
    return theme["dark" if night else "light"]["accent"]


def theme_gradient(theme_name: str, night: bool = False):
    """(start, end, angle) for a theme's own gradient, or None if it has none."""
    theme_name = ALIASES.get(theme_name, theme_name)
    theme = THEMES.get(theme_name) or THEMES["glass"]
    return parse_gradient(theme["dark" if night else "light"].get("accent-grad", ""))


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
