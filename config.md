# Awesome Dashboard — Configuration

Prefer the **Tools → Awesome Dashboard Settings…** dialog over editing this
JSON directly. See the [README](README.md) ([Tiếng Việt](README.vi.md)) for
what each feature does.

## Identity and language

- `userName` — display name in the greeting; empty uses the profile name.
- `customGreeting` — fixed greeting; empty gives a time-of-day greeting.
- `language` — `auto`, or any locale code present in `i18n/` (`en`, `vi`,
  `pt_BR`, `ja`).

## Dashboard

- `sidebarMode` — `full`, `compact` or `hidden`. While the sidebar is shown,
  the deck list and header card move into it.
- `showStats` / `showHeatmap` / `showPomodoro` / `showHabits` — toggle dashboard
  sections.
- `pomodoroFocusMinutes` / `pomodoroBreakMinutes` — session lengths in minutes.
- `events` — exam countdowns, each `{"name": "JLPT N2", "date": "2026-12-06"}`.

## Appearance

- `theme` — `terracotta`, `glass`, `matcha`, `aurora`, `sunset` or `sakura`.
  `aurora` and `sunset` paint their accent as a gradient. Retired keys still
  work: `aizome` and `sumi` map to `glass`, `washi` to `terracotta`, and
  `ajisai` to `aurora`.
- `customAccent` — `null`, or an accent override for the chosen theme:
  `{"accent": "#0071D3", "accent-soft": "rgba(0,113,211,0.14)",
  "accent-hover": "rgba(0,113,211,0.24)", "on-accent": "#ffffff"}`. Only the
  accent family is replaced; backgrounds, text and the new/learn/due colours
  still come from the theme. Edit it from **Settings → Appearance → Edit
  theme**.

  Add `"accent-grad": "linear-gradient(135deg, #6247E5 0%, #1FA9C4 100%)"` for a
  gradient. It is painted on buttons, pills and progress bars; `accent` stays the
  solid colour used for text, borders and the heatmap, and is best set to the
  midpoint of the two stops. An override without `accent-grad` clears the theme's
  own gradient, so a solid custom accent stays solid.

  The page background follows automatically: it is pulled toward each stop's hue
  at the background's own lightness, so it shifts colour without moving the text
  contrast. Nothing to configure.
- `styleOverview` — replace the deck overview with the redesigned screen. Also
  hides Anki's top and bottom bars there, since the page has its own back link
  and footer actions.
- `styleReviewer` — replace the review chrome with the in-page header and
  answer bar, and hide Anki's native bars during review.
- `backgroundImage` — filename of a background image inside the add-on's
  `user_files/` folder, or `""`. Set it from **Settings → Appearance**, which
  copies the file in; `user_files/` is the one directory Anki restores after an
  add-on update. Shown behind the dashboard and the deck screen only — the
  review screen keeps a plain background so answers stay legible.
- `backgroundDim` — 0–95. How much of the theme background is laid over the
  image. Higher is more readable, lower shows more of the photo.
- `cardOpacity` — 0–100. How solid the cards and sidebar are, with or without a
  background image. 100 is the plain opaque look. Below that they turn
  translucent, which is what makes an image visible through the page rather than
  only around its edges. Needs `color-mix`, so Chromium 111 (Qt 6.6) or newer —
  older webviews keep solid blocks, and **Settings → Appearance** hides the
  Blocks section entirely there rather than offering controls that do nothing.
  The About page reports which webview is running.
- `cardBlur` — 0–40 px. Blur applied to whatever shows through a translucent
  card. Higher smears the background into colour; **0 leaves it sharp**, which is
  the only setting where a picture can actually be made out through a card.
- `styleToolbar` — theme Anki's top toolbar.
- `styleSystemScreens` — theme Anki's other screens (webview CSS variables plus
  the Qt palette). Turning this off needs a restart to fully revert.
- `hideNativeBottomBar` — hide Anki's bottom button bar on the dashboard, which
  has its own action pills. Default on.
- `hideNativeToolbar` — hide Anki's top toolbar on the dashboard. Default off.

## Cards and scheduling

- `cardSkinDecks` — per-deck card skin, `{"<deck id>": true}`. Set from
  **Settings → Decks**; a top-level deck's setting covers its subdecks.
- `autoGrade` — auto-grading: the clock picks the rating, so reviewing is two
  keys (← didn't know, → knew it) and Again/Hard/Good/Easy are hidden. Needs
  `styleReviewer`, which draws the bar it lives in.
- `autoGradeEasyMax` / `autoGradeGoodMax` / `autoGradeHardMax` — seconds.
  Answer within the first and it is Easy, within the second Good, within the
  third Hard; past the third it is Again. `autoGradeHardMax` is also how long
  the question-side countdown runs, so the bar emptying *is* Again. The clock
  stops whenever Anki is not the active window, so stepping away costs nothing.
- `autoGradeDecks` — per-deck overrides, `{"<deck id>": {"enabled": true,
  "easyMax": 3}}`. Partial: anything the entry does not name is inherited from
  the parent deck, and from these global values above it. Set from
  **Settings → Decks**.

FSRS itself is stored by Anki, not here: the global switch lives in the
collection config and desired retention plus parameters live on each deck
preset. **Settings → FSRS** edits them through Anki's own API.

## Study modes

Quizlet-style Flashcards, Learn, Test and Match, opened from a deck's overview.
Which fields go on the front of a card and which on the back is worked out from
the card template; the pinned overrides live in the collection, not here, so
they sync and survive a reinstall. They are edited on the deck's own Study modes
screen, along with the session sizes below — the deck is already known there,
and a window of its own would only ask again. The first field on a side is the
one being asked about; the rest is shown alongside it, and a **Details** button
opens the whole card. A side holds at most two fields on the front and three on
the back, and never fewer than one.

**Settings → Study modes** keeps only `showQuizlet` and `qzGrade`: whether the
feature appears at all, and whether it may touch the scheduler.

- `showQuizlet` — whether the deck overview offers the study modes at all.
- `qzDirection` — which side is the prompt: `term`, `definition` or `mixed`.
- `qzTestLength` — questions in one Test, 1-100.
- `qzTestTypes` — question kinds a Test draws from, any of `tf`, `choice`,
  `typed`. They are dealt round-robin rather than at random, so a short test
  still covers every kind you asked for.
- `qzMatchPairs` — pairs in one Match round, 2-12.
- `qzSessionSize` — terms taken into one Learn session. `0` means the whole
  deck, which on a large deck is a session you will not finish.
- `qzGrade` — pass answers on to Anki's scheduler. **Off by default.** A study
  mode is practice; when this is on, only cards *already due* are graded
  (correct is Good, wrong is Again) — new cards are never introduced here,
  because that would spend the deck's daily allowance on a session you thought
  was practice.

## Internal

- `cardSkinDefault` — whether decks with no entry of their own use the card
  skin. `true` means every newly added deck starts with it on.
- `shownWelcome` — whether the first-run toast has been shown.
- `settingsPage` — nav page the settings dialog reopens on (`general`, `look`,
  `decks`, `fsrs`, `modes`, `events`, `habits`, `about`). Written by **Save**,
  so cancelling out of the dialog leaves it as it was.
- `debugFakeYears` — development only: synthesises several years of heatmap
  activity so the year picker can be tested. Display-only; the collection is
  never touched.
