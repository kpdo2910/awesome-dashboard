# Changelog

All notable changes to Awesome Dashboard are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Habit tracker. A strip on the dashboard ticks a habit off for today in one
  click, without reloading the page. Habits are yes/no or counted towards a
  target, and repeat daily, on chosen weekdays, or a number of times a week.
- Habit report with week, month and year views: a seven-day grid, a calendar
  per habit and a year strip, each with completion rate and streaks.
- Habits are stored in the collection, so they are included in `.colpkg`
  backups and in sync. Deleting one archives it and keeps its history; removing
  it permanently is a separate, confirmed action.
- A habit's colour can be any colour, not just one of the ten presets.

### Changed

- The habit manager is now just the list: add, delete, edit and reorder sit
  together as one monochrome row, and the streak has moved to the dashboard
  where habits are ticked. The report opens from the dashboard.
- Habit chips no longer show a minus control on hover; tapping past the target
  already wraps back to zero.
- "Show archived" in the report is a switch, matching the ones in Settings.
- About now reports the webview version. On builds too old for translucent
  blocks, that section of Appearance is hidden instead of shown doing nothing.

### Fixed

- Reset no longer replays the first-run welcome overlay.
- The habit editor's icon button no longer clips its emoji, and the icons in
  the picker no longer overlap each other.
- The icon picker's buttons are translated instead of showing Qt's own labels.
- Opening the habit report from the habit manager no longer freezes Anki.
- Habit history arriving from another computer through sync is no longer
  overwritten by the next tick on this one.
- The report no longer opens as a blank page: it is drawn over the dashboard
  rather than in a window of its own, shows the same loading indicator as the
  first-run overlay, and says so plainly if it cannot be built.
- The theme swatches are no longer clipped when selected.
- "Show archived" in the report works. It was inverted, so it appeared dead.
- The habit progress track and the unticked circles now take their colour from
  the theme instead of a fixed neutral grey.
- The report's year view is now the same continuous grid as the dashboard's
  activity heatmap, with no gap where a month label falls.

## [1.2.0] - 2026-08-08

### Added

- First-run onboarding: pick a theme, light or dark, sidebar mode and card
  skin, then a short welcome once everything is applied.
- About page in Settings, with version, package and Anki version.
- Settings reopens on the page you saved from; cancelling leaves it unchanged.
- Two gradient themes, Aurora and Sunset.
- Your own image as the background, with a dim setting.
- Blocks section in Appearance: make cards and the sidebar translucent, with an
  adjustable blur behind them. Works with or without a background image.
- The theme editor can build a gradient accent: two colours, an angle and a
  live preview.
- Reset in Settings: settings, study progress for chosen decks, or both.

### Changed

- A gradient accent now also tints the page behind it, not just the buttons.
- Translucent blocks now blur correctly on the deck screen too.
- Deck letter badges stay legible over a background image instead of
  dissolving into it.
- The heatmap's weekday labels no longer take a permanent column; they fade
  in over the grid on hover. Its scrollbar is now a thin themed rail.
- Glass is the default theme and leads the picker.
- Anki's top toolbar is hidden by default.
- Card skin is on by default for any deck you have not set explicitly,
  which includes every deck added from now on.
- Heatmap shades now scale to what a normal day looks like for you at that
  point in time, instead of fixed thresholds tuned for 20 new cards a day.
- Resetting everything now explains what it will erase before doing it.

### Removed

- The Ajisai and Sumi themes. Collections set to them move to Aurora and Glass.

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

[Unreleased]: https://github.com/kpdo2910/awesome-dashboard/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/kpdo2910/awesome-dashboard/releases/tag/v1.2.0
[1.1.0]: https://github.com/kpdo2910/awesome-dashboard/releases/tag/v1.1.0
[1.0.0]: https://github.com/kpdo2910/awesome-dashboard/releases/tag/v1.0.0
