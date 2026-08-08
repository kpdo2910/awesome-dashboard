# Changelog

All notable changes to Awesome Dashboard are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- First-run onboarding: pick a theme, light or dark, sidebar mode and card
  skin, then a short welcome once everything is applied.
- About page in Settings, with version, package and Anki version.
- Settings reopens on the page you saved from; cancelling leaves it unchanged.
- Reset in Settings: settings, study progress for chosen decks, or both.

### Changed

- Glass is the default theme and leads the picker.
- Anki's top toolbar is hidden by default.
- Card skin is on by default for any deck you have not set explicitly,
  which includes every deck added from now on.
- Heatmap shades now scale to what a normal day looks like for you at that
  point in time, instead of fixed thresholds tuned for 20 new cards a day.
- Resetting everything now explains what it will erase before doing it.

## [1.1.0] - 2026-08-08

### Added

- Pinned Pomodoro timer in the review screen header: countdown while running,
  one click to start, pause or skip.
- Themed deck-finished screen with a short celebration animation, plus Home and
  Custom study buttons.
- Anki's Custom Study dialog now follows the add-on's theme.

## [1.0.0] - 2026-08-08

First public release. Tested on Anki 26.08.

### Added

- Dashboard replacing Anki's deck screen: greeting, quick actions, stat cards
  and a year-by-year activity heatmap.
- Optional sidebar in two widths, with deck search and a tinted icon per deck.
- Redesigned deck overview with a 7-day forecast from the scheduler's due dates.
- In-page reviewer header and answer bar; rating intervals come from the
  scheduler, so they follow deck presets and FSRS.
- Optional per-deck card skin that rebuilds the answer from the note's fields,
  with a flip animation and swipe-to-rate.
- Pomodoro timer with a daily session count.
- Exam countdowns under the greeting.
- Settings dialog with five pages: General, Appearance, Decks, FSRS, Events.
- FSRS controls: global switch, desired retention, optimise and evaluate.
- Six themes with light and dark palettes, plus a System / Light / Dark switch
  that also retints Anki's own screens.
- English, Tiếng Việt and 日本語, following Anki's language by default.

[Unreleased]: https://github.com/kpdo2910/awesome-dashboard/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/kpdo2910/awesome-dashboard/releases/tag/v1.1.0
[1.0.0]: https://github.com/kpdo2910/awesome-dashboard/releases/tag/v1.0.0
