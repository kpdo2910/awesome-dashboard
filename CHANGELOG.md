# Changelog

All notable changes to Awesome Dashboard are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-08

First public release. Tested on Anki 26.08.

### Added

- **Dashboard** replacing Anki's deck screen — time-of-day greeting, quick
  actions, stat cards, and an activity heatmap that can be browsed year by year.
- **Optional sidebar** in two widths (full, or a compact icon rail). While shown,
  the deck list and header card move into it, with deck search and a tinted icon
  per deck.
- **Deck overview** — back link, deck icon and description, three count cards,
  one primary study button, a 7-day forecast built from the scheduler's real due
  dates, the subdeck list, and footer actions (options, custom study, rename,
  export, description).
- **Review screen chrome** drawn in the page — header (back, deck name, edit,
  more) and footer (remaining counts, then Show answer or the four rating
  buttons), so Anki's top toolbar and answer bar can step aside. Rating intervals
  come from the scheduler, so they follow deck presets and FSRS.
- **Card skin** (per-deck opt-in) rebuilding the answer from the note's fields —
  reading above the word, audio button, numbered meanings, image, collapsible
  example and notes — with a horizontal flip animation. Click or Space to flip;
  rate with the arrow keys or a mouse swipe.
- **Pomodoro timer** that keeps running while you study, with a daily session
  count.
- **Exam countdowns** under the greeting, turning orange inside 14 days.
- **Settings dialog** with five pages laid out like macOS System Settings:
  General, Appearance, Decks, FSRS and Events.
- **FSRS controls** driving Anki's native scheduler from one place — global
  on/off, per-preset desired retention, parameter optimisation and evaluation,
  and days since the last optimisation.
- **Six colour themes** (Terracotta, Glass — Apple HIG, Matcha, Ajisai, Sakura,
  Sumi), each with light and dark palettes, plus a System / Light / Dark switch
  that also changes Anki's own appearance. Switching cross-fades the open page
  instead of re-rendering it.
- **Optional theming of Anki's other screens** (Add, Browse, Stats, dialogs)
  through its CSS variables and the Qt palette.
- **Three languages** — English, Tiếng Việt and 日本語 — following Anki's
  language by default, each carrying its own month and weekday names, thousands
  separator and date order. Missing keys fall back to English, and
  `tools/check_locales.py` reports gaps.

[Unreleased]: https://github.com/kpdo2910/awesome-dashboard/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/kpdo2910/awesome-dashboard/releases/tag/v1.0.0
