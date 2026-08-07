# Awesome Dashboard — Configuration

Prefer the **Tools → Awesome Dashboard Settings…** dialog over editing this
JSON directly. See the [README](README.md) ([Tiếng Việt](README.vi.md)) for
what each feature does.

## Identity and language

- `userName` — display name in the greeting; empty uses the profile name.
- `customGreeting` — fixed greeting; empty gives a time-of-day greeting.
- `language` — `auto`, or any locale code present in `i18n/` (`en`, `vi`, `ja`).

## Dashboard

- `sidebarMode` — `full`, `compact` or `hidden`. While the sidebar is shown,
  the deck list and header card move into it.
- `showStats` / `showHeatmap` / `showPomodoro` — toggle dashboard sections.
- `pomodoroFocusMinutes` / `pomodoroBreakMinutes` — session lengths in minutes.
- `events` — exam countdowns, each `{"name": "JLPT N2", "date": "2026-12-06"}`.

## Appearance

- `theme` — `terracotta`, `glass`, `matcha`, `ajisai`, `sakura` or `sumi`.
  (`aizome` from older versions maps to `glass`.)
- `customAccent` — `null`, or an accent override for the chosen theme:
  `{"accent": "#0071D3", "accent-soft": "rgba(0,113,211,0.14)",
  "accent-hover": "rgba(0,113,211,0.24)", "on-accent": "#ffffff"}`. Only the
  accent family is replaced; backgrounds, text and the new/learn/due colours
  still come from the theme. Edit it from **Settings → Appearance → Edit
  theme**.
- `styleOverview` — replace the deck overview with the redesigned screen. Also
  hides Anki's top and bottom bars there, since the page has its own back link
  and footer actions.
- `styleReviewer` — replace the review chrome with the in-page header and
  answer bar, and hide Anki's native bars during review.
- `styleToolbar` — theme Anki's top toolbar.
- `styleSystemScreens` — theme Anki's other screens (webview CSS variables plus
  the Qt palette). Turning this off needs a restart to fully revert.
- `hideNativeBottomBar` — hide Anki's bottom button bar on the dashboard, which
  has its own action pills. Default on.
- `hideNativeToolbar` — hide Anki's top toolbar on the dashboard. Default off.

## Cards and scheduling

- `cardSkinDecks` — per-deck card skin, `{"<deck id>": true}`. Set from
  **Settings → Decks**; a top-level deck's setting covers its subdecks.

FSRS itself is stored by Anki, not here: the global switch lives in the
collection config and desired retention plus parameters live on each deck
preset. **Settings → FSRS** edits them through Anki's own API.

## Internal

- `shownWelcome` — whether the first-run toast has been shown.
- `debugFakeYears` — development only: synthesises several years of heatmap
  activity so the year picker can be tested. Display-only; the collection is
  never touched.
