/* ============================================================
   quizlet.js — draws the study modes. Every rule and every
   number arrives from screens/quizlet.py; this file only turns
   a payload into a screen.

   The one exception is deliberate: Match runs its clock and its
   tile matching here and only sends the final time back. A
   round trip per tap would make a timed game feel broken, and
   there is no rule in it to keep honest — the pairs were
   decided in Python before the grid was drawn.

   Learn and Test answer through pycmd on purpose: the session
   is the thing being resumed days later, so it may only ever be
   changed on the side that can write it.
   ============================================================ */

(function () {
  "use strict";

  var AwdQz = (window.AwdQz = window.AwdQz || {});

  var data = null;
  var strings = {};

  /* Client-side state, none of it authoritative: the flashcard position, the
     half-finished Match grid, and whether a Learn verdict is still on screen. */
  var cards = { index: 0, flipped: false, order: null };
  var match = { picked: null, done: 0, start: 0, timer: null, locked: false };
  var showingFeedback = false;

  function host() {
    return document.getElementById("awd-qz");
  }

  function send(command) {
    if (typeof pycmd === "function") pycmd("awd:qz:" + command);
  }

  function i18n(key, vars) {
    var text = strings[key] || "";
    if (!vars) return text;
    return text.replace(/\{(\w+)\}/g, function (whole, name) {
      return Object.prototype.hasOwnProperty.call(vars, name)
        ? String(vars[name])
        : whole;
    });
  }

  function escapeHtml(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* Field markup arrives already filtered by features/quizlet/fields.safe_html
     — scripts, styles and every stray attribute are gone before it gets here,
     which is what makes it safe to put in innerHTML at all. */
  function fieldHtml(value) {
    return value || "";
  }

  var ICONS = {
    back: '<path d="M15 5.5 8.5 12l6.5 6.5"/>',
    gear:
      '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    left: '<path d="M15 5.5 8.5 12l6.5 6.5"/>',
    right: '<path d="M9 5.5 15.5 12 9 18.5"/>',
    shuffle:
      '<path d="M16 3h5v5"/><path d="M4 20 21 3"/><path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/>',
    tick: '<path d="M4 12.5 9 17.5 20 6.5"/>',
    cross: '<path d="M6 6l12 12M18 6L6 18"/>',
    cards: '<rect x="3" y="5" width="13" height="10" rx="2"/><path d="M8 19h13V9"/>',
    learn: '<path d="M12 3 2 8l10 5 10-5z"/><path d="M6 10.5V16c0 1.7 2.7 3 6 3s6-1.3 6-3v-5.5"/>',
    test: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 14.5l1.8 1.8 3.5-3.6"/>',
    tickmark: '<path d="M5 12.5 10 17.5 19 7"/>',
    minus: '<path d="M6 12h12"/>',
    plus: '<path d="M12 6v12M6 12h12"/>',
    match: '<rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/>',
  };

  function svg(name, extra) {
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="' +
      (extra || 2) +
      '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      ICONS[name] +
      "</svg>"
    );
  }

  /* ---------- shared chrome ---------- */

  function header(title, backCommand) {
    return (
      '<header class="awd-qz-head">' +
      '<span class="awd-qz-back" data-cmd="' +
      escapeHtml(backCommand) +
      '">' +
      svg("back", 2.4) +
      "<span>" +
      escapeHtml(i18n("qz_back")) +
      "</span></span>" +
      '<span class="awd-qz-head-title">' +
      escapeHtml(title || "") +
      "</span>" +
      '<span class="awd-qz-icon" data-cmd="setup" title="' +
      escapeHtml(i18n("qz_settings")) +
      '">' +
      svg("gear", 1.8) +
      "</span></header>"
    );
  }

  /* The review screen's own play button — same class, same glyph, so it is
     the same control wherever it appears. Only the command differs: the
     reviewer knows the filename, a study mode knows the card and the side. */
  function audioButton(side, cid, files) {
    if (!files || !files.length || cid == null) return "";
    return (
      '<button class="awd-skin-audio" data-cmd="play:' +
      cid +
      ":" +
      side +
      '" title="' +
      escapeHtml(i18n("qz_play")) +
      '">' +
      '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">' +
      '<path d="M8 5.5v13l11-6.5z"/></svg>' +
      "</button>"
    );
  }

  /* A side is a set of fields: the first is the one being asked about, the
     rest is context. Both the question and the reveal are drawn from the same
     shape, so what the user chose on the settings page is what every mode
     shows. */
  function stackRows(side, skipKey) {
    var rows = (side && side.rows) || [];
    if (skipKey) rows = rows.slice(1);
    if (!rows.length) return "";
    return (
      '<div class="awd-qz-stack">' +
      rows
        .map(function (row) {
          return (
            '<div class="awd-qz-row"><div class="awd-qz-row-label">' +
            escapeHtml(row.label) +
            '</div><div class="awd-qz-row-body">' +
            fieldHtml(row.html) +
            "</div></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function keyBlock(side, cid, small) {
    return (
      '<div class="awd-qz-prompt' +
      (small ? " small" : "") +
      '"><div>' +
      fieldHtml(side.keyHtml) +
      "</div>" +
      audioButton(side.side || "front", cid, side.audio) +
      "</div>"
    );
  }

  function promptBlock(side, cid, small) {
    return keyBlock(side, cid, small) + stackRows(side, true);
  }

  /* The full card, dressed exactly as the review screen dresses it — same
     markup, same stylesheet, built by screens/card_skin.answer_body. Behind a
     button because a study mode is meant to ask one thing at a time; the whole
     card belongs to the moment you want to look it up, not to every answer. */
  function detailsBlock(skin) {
    if (!skin) return "";
    return (
      '<div class="awd-qz-details">' +
      '<button class="awd-qz-btn ghost" data-details="1">' +
      escapeHtml(i18n("qz_details")) +
      "</button>" +
      '<div class="awd-qz-detail" hidden>' +
      '<div class="awd-skin-card answer">' +
      skin +
      "</div></div></div>"
    );
  }

  /* ---------- picker ---------- */

  var MODE_ICONS = { cards: "cards", learn: "learn", test: "test", match: "match" };

  function modeCard(mode, best) {
    return (
      '<button class="awd-qz-mode" data-mode="' +
      mode +
      '">' +
      '<span class="awd-qz-mode-ic">' +
      svg(MODE_ICONS[mode]) +
      "</span><span><span class=\"awd-qz-mode-name\">" +
      escapeHtml(i18n("qz_" + mode)) +
      '</span><span class="awd-qz-mode-desc">' +
      escapeHtml(i18n("qz_" + mode + "_desc")) +
      "</span>" +
      (best ? '<span class="awd-qz-mode-best">' + escapeHtml(best) + "</span>" : "") +
      "</span></button>"
    );
  }

  function segment(option, current, values, labels) {
    var chosen = Math.max(0, values.indexOf(current));
    return (
      '<span class="awd-qz-seg" style="--awd-seg-n:' +
      values.length +
      ";--awd-seg-i:" +
      chosen +
      '"><i class="awd-qz-seg-pill"></i>' +
      values
        .map(function (value, index) {
          return (
            '<button data-opt="' +
            option +
            '" data-value="' +
            escapeHtml(value) +
            '" class="' +
            (value === current ? "on" : "") +
            '">' +
            escapeHtml(labels[index]) +
            "</button>"
          );
        })
        .join("") +
      "</span>"
    );
  }

  function drawPicker() {
    var pair = data.pair || {};
    var record = data.record || {};
    var options = data.options || {};
    var parts = [header(data.deck, "exit")];

    if (pair.term) {
      parts.push(
        '<section class="awd-qz-card">' +
          '<div class="awd-qz-pair">' +
          "<span>" +
          escapeHtml(i18n("qz_pair_label")) +
          "</span><b>" +
          escapeHtml(pair.term) +
          '</b><span class="awd-qz-pair-arrow">→</span><b>' +
          escapeHtml(pair.def) +
          "</b>" +
          (pair.variants
            ? '<span class="awd-qz-pair-arrow">' +
              escapeHtml(i18n("qz_pair_more", { n: pair.variants })) +
              "</span>"
            : "") +
          '<span class="awd-qz-pair-change" data-cmd="setup">' +
          escapeHtml(i18n("qz_change")) +
          "</span></div>" +
          '<div class="awd-qz-sample"><span>' +
          escapeHtml(pair.sampleTerm) +
          '</span><span class="awd-qz-pair-arrow">→</span><span>' +
          escapeHtml(pair.sampleDef) +
          "</span></div></section>"
      );
    }

    if (data.resume) {
      var progress = data.resume.progress || {};
      parts.push(
        '<section class="awd-qz-card awd-qz-resume">' +
          '<div class="awd-qz-resume-text">' +
          '<div class="awd-qz-resume-title">' +
          escapeHtml(i18n("qz_resume")) +
          "</div>" +
          '<div class="awd-qz-resume-body">' +
          escapeHtml(
            i18n("qz_resume_body", {
              percent: progress.percent || 0,
              total: progress.total || 0,
            })
          ) +
          "</div></div>" +
          '<button class="awd-qz-btn ghost" data-cmd="restart">' +
          escapeHtml(i18n("qz_restart")) +
          "</button>" +
          '<button class="awd-qz-btn" data-cmd="start:learn:resume">' +
          escapeHtml(i18n("qz_start")) +
          "</button></section>"
      );
    }

    var bests = {
      match: record.match != null ? i18n("qz_best", { value: record.match + "s" }) : "",
      test: record.test != null ? i18n("qz_best", { value: record.test + "%" }) : "",
    };
    parts.push(
      '<div class="awd-qz-modes">' +
        ["cards", "learn", "test", "match"]
          .map(function (mode) {
            return modeCard(mode, bests[mode] || "");
          })
          .join("") +
        "</div>"
    );

    parts.push(
      '<div class="awd-qz-opts"><span>' +
        escapeHtml(i18n("qz_direction")) +
        "</span>" +
        segment(
          "direction",
          options.direction,
          ["term", "definition", "mixed"],
          [i18n("qz_dir_term"), i18n("qz_dir_def"), i18n("qz_dir_mixed")]
        ) +
        "</div>"
    );

    var meta = i18n("qz_terms", { n: data.total || 0 });
    if (data.skipped) meta += " · " + i18n("qz_skipped", { n: data.skipped });
    parts.push('<div class="awd-qz-meta">' + escapeHtml(meta) + "</div>");

    return parts.join("");
  }

  function drawEmpty() {
    return (
      header(data.deck, "exit") +
      '<section class="awd-qz-card awd-qz-empty">' +
      '<div class="awd-qz-empty-title">' +
      escapeHtml(i18n("qz_empty_title")) +
      "</div>" +
      '<div class="awd-qz-empty-body">' +
      escapeHtml(i18n("qz_empty_body")) +
      "</div>" +
      '<div class="awd-qz-actions"><button class="awd-qz-btn ghost" data-cmd="setup">' +
      escapeHtml(i18n("qz_settings")) +
      "</button></div></section>"
    );
  }

  /* ---------- setup ---------- */

  /* A side that is full greys out its remaining boxes rather than letting a
     click do nothing — a control that refuses has to show why, and the cap in
     the column header is the explanation. */
  function tick(card, field, side, chosen, caps) {
    var on = !!field[side];
    var other = side === "front" ? "back" : "front";
    /* Three reasons a box will not move, all of them shown rather than
       enforced silently: the side is full, this is the last field on the side,
       or moving it here would strip the other side down to nothing. */
    var locked = on
      ? chosen[side] <= 1
      : chosen[side] >= caps[side] || (field[other] && chosen[other] <= 1);
    return (
      '<button class="awd-qz-tick' +
      (on ? " on" : "") +
      (locked ? " locked" : "") +
      '"' +
      (locked ? " disabled" : "") +
      ' data-field=\'' +
      escapeHtml(
        JSON.stringify({ nt: card.nt, field: field.name, side: side, on: !on })
      ) +
      "'>" +
      (on ? svg("tickmark", 3) : "") +
      "</button>"
    );
  }

  function cardSetup(card) {
    var chosen = { front: 0, back: 0 };
    (card.fields || []).forEach(function (field) {
      if (field.front) chosen.front += 1;
      if (field.back) chosen.back += 1;
    });
    var caps = { front: data.maxFront, back: data.maxBack };
    var rows = (card.fields || [])
      .map(function (field) {
        return (
          '<div class="awd-qz-fieldrow"><span>' +
          escapeHtml(field.name) +
          "</span>" +
          tick(card, field, "front", chosen, caps) +
          tick(card, field, "back", chosen, caps) +
          "</div>"
        );
      })
      .join("");
    return (
      '<section class="awd-qz-card awd-qz-setup">' +
      '<div class="awd-qz-setup-head"><span class="awd-qz-setup-title">' +
      escapeHtml(card.label) +
      '</span><span class="awd-qz-setup-count">' +
      escapeHtml(i18n("qz_terms", { n: card.count })) +
      "</span>" +
      (card.pinned
        ? '<button class="awd-qz-link" data-fieldauto=\'' +
          escapeHtml(JSON.stringify({ nt: card.nt })) +
          "'>" +
          escapeHtml(i18n("qz_reset_auto")) +
          "</button>"
        : "") +
      "</div>" +
      '<div class="awd-qz-fieldgrid"><div class="awd-qz-fieldrow head"><span>' +
      escapeHtml(i18n("qz_field")) +
      "</span><span>" +
      escapeHtml(i18n("qz_side_front")) +
      '<i>' +
      escapeHtml(i18n("qz_side_max", { n: data.maxFront })) +
      "</i></span><span>" +
      escapeHtml(i18n("qz_side_back")) +
      '<i>' +
      escapeHtml(i18n("qz_side_max", { n: data.maxBack })) +
      "</i></span></div>" +
      rows +
      "</div>" +
      '<div class="awd-qz-sample"><span>' +
      escapeHtml(card.sample.front) +
      '</span><span class="awd-qz-pair-arrow">→</span><span>' +
      escapeHtml(card.sample.back) +
      "</span></div></section>"
    );
  }

  function stepper(option, value, label, display) {
    return (
      '<div class="awd-qz-step"><span class="awd-qz-step-label">' +
      escapeHtml(label) +
      '</span><button class="awd-qz-round small" data-step-opt="' +
      option +
      '" data-dir="-1">' +
      svg("minus", 2.4) +
      '</button><span class="awd-qz-step-value">' +
      escapeHtml(display) +
      '</span><button class="awd-qz-round small" data-step-opt="' +
      option +
      '" data-dir="1">' +
      svg("plus", 2.4) +
      "</button></div>"
    );
  }

  /* A deck of its own has one note type and one block. A parent deck gathers
     its subdecks, so it can have several with nothing in common — `Front`/`Back`
     next to `tu vung`/`nghia` — and a single grid could not represent them. The
     commonest one stands alone and the rest fold away, so the usual deck still
     reads as one setting while a mixed one keeps every card reachable. */
  function otherTypes(cards) {
    if (!cards.length) return "";
    var rest = cards.slice(1);
    if (!rest.length) return cardSetup(cards[0]);
    return (
      cardSetup(cards[0]) +
      '<div class="awd-qz-details"><button class="awd-qz-btn ghost" data-details="1">' +
      escapeHtml(i18n("qz_other_types", { n: rest.length })) +
      '</button><div class="awd-qz-detail" hidden>' +
      rest.map(cardSetup).join("") +
      "</div></div>"
    );
  }

  var TEST_KINDS = ["tf", "choice", "typed"];

  function drawSetup() {
    var options = data.options || {};
    var kinds = options.testTypes || [];
    return (
      header(data.deck, "picker") +
      otherTypes(data.cards || []) +
      '<div class="awd-qz-meta">' +
      escapeHtml(i18n("qz_fieldmap_desc")) +
      "</div>" +
      '<section class="awd-qz-card awd-qz-setup">' +
      '<div class="awd-qz-setup-title">' +
      escapeHtml(i18n("qz_sizes")) +
      "</div>" +
      '<div class="awd-qz-opts start"><span>' +
      escapeHtml(i18n("qz_direction")) +
      "</span>" +
      segment(
        "direction",
        options.direction,
        ["term", "definition", "mixed"],
        [i18n("qz_dir_term"), i18n("qz_dir_def"), i18n("qz_dir_mixed")]
      ) +
      "</div>" +
      stepper(
        "sessionSize",
        options.sessionSize,
        i18n("qz_session_size"),
        options.sessionSize ? String(options.sessionSize) : i18n("qz_whole_deck")
      ) +
      stepper("testLength", options.testLength, i18n("qz_length"),
              String(options.testLength)) +
      stepper("matchPairs", options.matchPairs, i18n("qz_pairs"),
              String(options.matchPairs)) +
      '<div class="awd-qz-step"><span class="awd-qz-step-label">' +
      escapeHtml(i18n("qz_test")) +
      '</span><span class="awd-qz-kinds">' +
      TEST_KINDS.map(function (kind) {
        return (
          '<button class="awd-qz-chip' +
          (kinds.indexOf(kind) >= 0 ? " on" : "") +
          '" data-kind="' +
          kind +
          '">' +
          escapeHtml(i18n("qz_type_" + kind)) +
          "</button>"
        );
      }).join("") +
      "</span></div>" +
      '<div class="awd-qz-hintline">' +
      escapeHtml(i18n("qz_types_hint")) +
      "</div></section>"
    );
  }

  /* ---------- flashcards ---------- */

  function currentCard() {
    var list = data.cards || [];
    if (!list.length) return null;
    var order = cards.order || [];
    var position = order.length ? order[cards.index % order.length] : cards.index;
    return list[position] || null;
  }

  function drawCards() {
    var list = data.cards || [];
    if (!cards.order || cards.order.length !== list.length) {
      cards.order = list.map(function (_unused, index) {
        return index;
      });
    }
    var card = currentCard();
    if (!card) return drawEmpty();
    return (
      header(data.deck, "picker") +
      '<div class="awd-flip-scene" id="awd-qz-flip">' +
      '<div class="awd-flip-inner' +
      (cards.flipped ? " flipped" : "") +
      '" id="awd-qz-flip-inner">' +
      '<div class="awd-flip-face front"><div class="awd-skin-card question">' +
      promptBlock(card.front, card.cid, false) +
      "</div></div>" +
      '<div class="awd-flip-face back"><div class="awd-skin-card answer">' +
      keyBlock(card.back, card.cid, true) +
      stackRows(card.back, true) +
      detailsBlock(card.skin) +
      "</div></div></div></div>" +
      '<div class="awd-qz-nav">' +
      '<button class="awd-qz-round" data-step="-1">' +
      svg("left", 2.4) +
      "</button>" +
      '<span class="awd-qz-count">' +
      escapeHtml(
        i18n("qz_of", { n: cards.index + 1, total: list.length })
      ) +
      "</span>" +
      '<button class="awd-qz-round" data-step="1">' +
      svg("right", 2.4) +
      "</button>" +
      '<button class="awd-qz-round" data-shuffle="1" title="' +
      escapeHtml(i18n("qz_shuffle")) +
      '">' +
      svg("shuffle") +
      "</button></div>" +
      '<div class="awd-qz-meta">' +
      escapeHtml(i18n("qz_flip")) +
      "</div>"
    );
  }

  /* Same list as card_skin.js `onInteractive`, and for the same reason: the
     flip is the *card's* affordance, so anything inside it that does its own
     thing on a click keeps that click. `details` and `summary` are the ones
     that matter here — the reveal's collapsible example sits inside the card,
     and without this, opening it turns the card over instead. */
  function onInteractive(target) {
    return (
      target.closest &&
      target.closest(
        "a, button, details, summary, input, textarea, select, audio, video," +
        " [contenteditable]"
      )
    );
  }

  function flipCard() {
    cards.flipped = !cards.flipped;
    var inner = document.getElementById("awd-qz-flip-inner");
    if (inner) inner.classList.toggle("flipped", cards.flipped);
  }

  function step(delta) {
    var list = (data.cards || []).length;
    if (!list) return;
    cards.index = (cards.index + delta + list) % list;
    cards.flipped = false;
    send("index:" + cards.index);
    draw();
  }

  function shuffle() {
    var order = cards.order || [];
    for (var i = order.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var swap = order[i];
      order[i] = order[j];
      order[j] = swap;
    }
    cards.order = order;
    cards.index = 0;
    cards.flipped = false;
    draw();
  }

  /* ---------- learn ---------- */

  function progressBar(progress) {
    return (
      '<div class="awd-qz-topbar"><div class="awd-qz-track"><i style="width:' +
      (progress.percent || 0) +
      '%"></i></div></div>' +
      '<div class="awd-qz-status"><span>' +
      escapeHtml(i18n("qz_round", { n: progress.round || 1 })) +
      "</span><span>" +
      escapeHtml(
        i18n("qz_mastered", {
          n: progress.mastered || 0,
          total: progress.total || 0,
        })
      ) +
      "</span>" +
      (progress.streak
        ? "<span><b>" +
          escapeHtml(i18n("qz_streak", { n: progress.streak })) +
          "</b></span>"
        : "") +
      "</div>"
    );
  }

  function optionButtons(options) {
    return (
      '<div class="awd-qz-options">' +
      options
        .map(function (option, index) {
          return (
            '<button class="awd-qz-opt" data-choice="' +
            index +
            '"><span class="awd-qz-opt-key">' +
            (index + 1) +
            "</span><span>" +
            fieldHtml(option.html) +
            "</span></button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function trueFalse(shown) {
    return (
      '<div class="awd-qz-kind">' +
      escapeHtml(i18n("qz_tf_prompt")) +
      "</div>" +
      '<div class="awd-qz-prompt small"><div>' +
      fieldHtml(shown.html) +
      "</div></div>" +
      '<div class="awd-qz-options">' +
      '<button class="awd-qz-opt" data-tf="1"><span class="awd-qz-opt-key">1</span><span>' +
      escapeHtml(i18n("qz_true")) +
      "</span></button>" +
      '<button class="awd-qz-opt" data-tf="0"><span class="awd-qz-opt-key">2</span><span>' +
      escapeHtml(i18n("qz_false")) +
      "</span></button></div>"
    );
  }

  function typedBox(question) {
    return (
      '<div class="awd-qz-type">' +
      '<div class="awd-qz-kind">' +
      escapeHtml(i18n("qz_type_prompt")) +
      "</div>" +
      '<input class="awd-qz-input" id="awd-qz-input" autocomplete="off" ' +
      'autocorrect="off" autocapitalize="off" spellcheck="false">' +
      '<div class="awd-qz-typerow">' +
      '<button class="awd-qz-btn ghost" data-hint="1">' +
      escapeHtml(i18n("qz_hint")) +
      "</button>" +
      '<button class="awd-qz-btn ghost" data-skip="1">' +
      escapeHtml(i18n("qz_dont_know")) +
      "</button>" +
      '<button class="awd-qz-btn" data-submit="1">' +
      escapeHtml(i18n("qz_submit")) +
      "</button></div>" +
      '<div class="awd-qz-hint" id="awd-qz-hint" hidden>' +
      escapeHtml(question.hint || "") +
      "</div></div>"
    );
  }

  function activity(question) {
    if (question.kind === "tf") return trueFalse(question.shown);
    if (question.kind === "choice") return optionButtons(question.options || []);
    return typedBox(question);
  }

  function verdictLine(feedback) {
    var kind = feedback.correct ? (feedback.exact ? "ok" : "almost") : "no";
    var label = feedback.correct
      ? feedback.exact
        ? i18n("qz_correct")
        : i18n("qz_almost")
      : i18n("qz_incorrect");
    return (
      '<div class="awd-qz-verdict ' +
      kind +
      '">' +
      svg(feedback.correct ? "tick" : "cross", 2.6) +
      "<span>" +
      escapeHtml(label) +
      "</span></div>"
    );
  }

  function drawFeedback(feedback, progress) {
    var given = "";
    if (feedback.given && (!feedback.correct || !feedback.exact)) {
      given =
        "<span>" +
        escapeHtml(i18n("qz_your_answer")) +
        " <s>" +
        escapeHtml(feedback.given) +
        "</s></span>";
    }
    return (
      progressBar(progress) +
      '<section class="awd-qz-card awd-qz-feedback">' +
      verdictLine(feedback) +
      '<div class="awd-qz-was"><span>' +
      escapeHtml(i18n("qz_answer_was")) +
      "</span><strong>" +
      fieldHtml(feedback.expected.html) +
      "</strong>" +
      given +
      "</div>" +
      stackRows(feedback.answer, true) +
      detailsBlock(feedback.skin) +
      "</section>" +
      '<div class="awd-qz-actions"><button class="awd-qz-btn" data-cmd="continue">' +
      escapeHtml(i18n("qz_continue")) +
      "</button></div>"
    );
  }

  function drawLearn() {
    var progress = data.progress || {};
    var question = data.question;
    if (!question) return drawRoundDone();
    return (
      header(data.deck, "picker") +
      progressBar(progress) +
      '<section class="awd-qz-card awd-qz-q">' +
      promptBlock(question.prompt, question.cid, question.kind === "tf") +
      activity(question) +
      "</section>"
    );
  }

  function drawRoundDone() {
    var progress = data.progress || {};
    return (
      header(data.deck, "picker") +
      progressBar(progress) +
      '<section class="awd-qz-card awd-qz-result">' +
      '<div class="awd-qz-result-big">' +
      (progress.percent || 0) +
      "%</div>" +
      '<div class="awd-qz-result-title">' +
      escapeHtml(i18n("qz_round_done")) +
      "</div>" +
      '<div class="awd-qz-result-note">' +
      escapeHtml(
        i18n("qz_round_done_body", {
          n: progress.mastered || 0,
          total: progress.total || 0,
        })
      ) +
      "</div>" +
      '<div class="awd-qz-actions">' +
      '<button class="awd-qz-btn ghost" data-cmd="picker">' +
      escapeHtml(i18n("qz_exit")) +
      "</button>" +
      '<button class="awd-qz-btn" data-cmd="round">' +
      escapeHtml(i18n("qz_continue")) +
      "</button></div></section>"
    );
  }

  function drawLearnDone() {
    var progress = data.progress || {};
    return (
      header(data.deck, "picker") +
      '<section class="awd-qz-card awd-qz-result">' +
      '<div class="awd-qz-result-big">100%</div>' +
      '<div class="awd-qz-result-title">' +
      escapeHtml(i18n("qz_learn_done")) +
      "</div>" +
      '<div class="awd-qz-result-note">' +
      escapeHtml(i18n("qz_learn_done_body", { total: progress.total || 0 })) +
      "</div>" +
      '<div class="awd-qz-actions">' +
      '<button class="awd-qz-btn ghost" data-cmd="picker">' +
      escapeHtml(i18n("qz_exit")) +
      "</button>" +
      '<button class="awd-qz-btn" data-cmd="restart">' +
      escapeHtml(i18n("qz_again")) +
      "</button></div></section>"
    );
  }

  /* ---------- test ---------- */

  function drawTest() {
    var question = data.question;
    if (!question) return drawEmpty();
    var done = question.index / Math.max(1, question.total);
    return (
      header(data.deck, "picker") +
      '<div class="awd-qz-topbar"><div class="awd-qz-track"><i style="width:' +
      Math.round(done * 100) +
      '%"></i></div></div>' +
      '<div class="awd-qz-status"><span>' +
      escapeHtml(
        i18n("qz_question", { n: question.index + 1, total: question.total })
      ) +
      "</span></div>" +
      '<section class="awd-qz-card awd-qz-q">' +
      promptBlock(question.prompt, question.cid, question.kind === "tf") +
      (question.kind === "tf"
        ? trueFalse(question.shown)
        : question.kind === "choice"
        ? optionButtons(question.options || [])
        : typedBox(question)) +
      "</section>"
    );
  }

  function drawTestDone() {
    var score = data.score || {};
    var rows = (data.review || [])
      .map(function (row) {
        return (
          '<div class="awd-qz-review-row ' +
          (row.correct ? "ok" : "no") +
          '"><span class="awd-qz-review-mark">' +
          (row.correct ? "✓" : "✕") +
          "</span><span>" +
          escapeHtml(row.prompt) +
          "</span><span>" +
          escapeHtml(row.expected) +
          (row.correct || !row.given
            ? ""
            : ' <span class="awd-qz-review-given">(' +
              escapeHtml(row.given) +
              ")</span>") +
          "</span></div>"
        );
      })
      .join("");
    return (
      header(data.deck, "picker") +
      '<section class="awd-qz-card awd-qz-result">' +
      '<div class="awd-qz-result-big">' +
      (score.percent || 0) +
      "%</div>" +
      '<div class="awd-qz-result-title">' +
      escapeHtml(i18n("qz_test_done")) +
      "</div>" +
      '<div class="awd-qz-result-note">' +
      escapeHtml(i18n("qz_score", { n: score.right || 0, total: score.total || 0 })) +
      "</div>" +
      (data.beaten
        ? '<span class="awd-qz-record">' + escapeHtml(i18n("qz_new_record")) + "</span>"
        : "") +
      '<div class="awd-qz-actions">' +
      '<button class="awd-qz-btn ghost" data-cmd="picker">' +
      escapeHtml(i18n("qz_exit")) +
      "</button>" +
      '<button class="awd-qz-btn" data-cmd="start:test">' +
      escapeHtml(i18n("qz_again")) +
      "</button></div></section>" +
      '<section class="awd-qz-card"><div class="awd-qz-kind">' +
      escapeHtml(i18n("qz_review")) +
      '</div><div class="awd-qz-review">' +
      rows +
      "</div></section>"
    );
  }

  /* ---------- match ---------- */

  function drawMatch() {
    var tiles = data.tiles || [];
    return (
      header(data.deck, "picker") +
      '<div class="awd-qz-timer" id="awd-qz-timer">0.0s</div>' +
      '<div class="awd-qz-meta">' +
      escapeHtml(i18n("qz_match_intro")) +
      "</div>" +
      '<div class="awd-qz-grid" id="awd-qz-grid">' +
      tiles
        .map(function (tile, index) {
          return (
            '<button class="awd-qz-tile" data-tile="' +
            index +
            '" data-pair="' +
            tile.pair +
            '"><span>' +
            fieldHtml(tile.html) +
            "</span></button>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function tickTimer() {
    var box = document.getElementById("awd-qz-timer");
    if (!box || !match.start) return;
    box.textContent = ((Date.now() - match.start) / 1000).toFixed(1) + "s";
  }

  function startTimer() {
    stopTimer();
    match.start = Date.now();
    match.timer = setInterval(tickTimer, 100);
  }

  function stopTimer() {
    if (match.timer) clearInterval(match.timer);
    match.timer = null;
  }

  function onTile(button) {
    if (match.locked || button.classList.contains("gone")) return;
    if (!match.start) startTimer();
    if (button === match.picked) {
      button.classList.remove("picked");
      match.picked = null;
      return;
    }
    if (!match.picked) {
      button.classList.add("picked");
      match.picked = button;
      return;
    }
    var first = match.picked;
    match.picked = null;
    if (first.dataset.pair === button.dataset.pair) {
      first.classList.remove("picked");
      first.classList.add("gone");
      button.classList.add("gone");
      match.done += 1;
      var total = (data.tiles || []).length / 2;
      if (match.done >= total) finishMatch();
      return;
    }
    /* Both tiles flash, then clear. Locking for the flash keeps a fast series
       of clicks from starting a third selection mid-animation, which would
       leave a tile stuck in the picked state. */
    match.locked = true;
    first.classList.remove("picked");
    first.classList.add("miss");
    button.classList.add("miss");
    setTimeout(function () {
      first.classList.remove("miss");
      button.classList.remove("miss");
      match.locked = false;
    }, 320);
  }

  function finishMatch() {
    stopTimer();
    var seconds = (Date.now() - match.start) / 1000;
    send("match:" + seconds.toFixed(2));
  }

  function drawMatchDone() {
    return (
      header(data.deck, "picker") +
      '<section class="awd-qz-card awd-qz-result">' +
      '<div class="awd-qz-result-big">' +
      escapeHtml(String(data.seconds)) +
      "s</div>" +
      '<div class="awd-qz-result-title">' +
      escapeHtml(i18n("qz_match_done")) +
      "</div>" +
      (data.record != null
        ? '<div class="awd-qz-result-note">' +
          escapeHtml(i18n("qz_best", { value: data.record + "s" })) +
          "</div>"
        : "") +
      (data.beaten
        ? '<span class="awd-qz-record">' + escapeHtml(i18n("qz_new_record")) + "</span>"
        : "") +
      '<div class="awd-qz-actions">' +
      '<button class="awd-qz-btn ghost" data-cmd="picker">' +
      escapeHtml(i18n("qz_exit")) +
      "</button>" +
      '<button class="awd-qz-btn" data-cmd="start:match">' +
      escapeHtml(i18n("qz_again")) +
      "</button></div></section>"
    );
  }

  /* ---------- draw ---------- */

  var SCREENS = {
    picker: drawPicker,
    empty: drawEmpty,
    cards: drawCards,
    learn: drawLearn,
    learnRound: drawRoundDone,
    learnDone: drawLearnDone,
    test: drawTest,
    testDone: drawTestDone,
    setup: drawSetup,
    match: drawMatch,
    matchDone: drawMatchDone,
  };

  function draw() {
    var where = host();
    if (!where || !data) return;
    stopTimer();
    /* A verdict outranks the screen it belongs to. The last answer of a round
       finishes it, so the payload comes back as "learnRound" — showing that
       straight away would grade the answer silently and move on. */
    var render =
      data.feedback && showingFeedback && (data.screen || "").indexOf("learn") === 0
        ? function () {
            return header(data.deck, "picker") + drawFeedback(data.feedback, data.progress || {});
          }
        : SCREENS[data.screen] || drawPicker;
    where.innerHTML = render();
    if (data.screen === "match") resetMatch();
    focusInput();
  }

  function resetMatch() {
    /* The clock starts on the first tile, not on render: a grid that is already
       counting while the page is still settling records a time the player never
       had a chance at. */
    match = { picked: null, done: 0, start: 0, timer: null, locked: false };
    var box = document.getElementById("awd-qz-timer");
    if (box) box.textContent = "0.0s";
  }

  function focusInput() {
    var input = document.getElementById("awd-qz-input");
    if (input) input.focus();
  }

  /* ---------- events ---------- */

  function answer(payload) {
    send("answer:" + JSON.stringify(payload));
  }

  function submitTyped(skip) {
    var input = document.getElementById("awd-qz-input");
    var text = input ? input.value : "";
    /* An empty answer is refused in Learn, where "Don't know" is the way past a
       term you cannot recall, and accepted in Test, which has no such button —
       there, refusing silently would leave the question with no way out at
       all. */
    if (!skip && !text.trim() && data.screen !== "test") return;
    answer({ text: text, skip: !!skip });
  }

  function onClick(event) {
    var where = host();
    if (!where || !event.target || !event.target.closest) return;
    if (!where.contains(event.target)) return;

    var target = event.target.closest("[data-cmd]");
    if (target) {
      var command = target.getAttribute("data-cmd");
      if (command === "continue") {
        showingFeedback = false;
        data.feedback = null;
        draw();
        return;
      }
      send(command);
      return;
    }

    var mode = event.target.closest("[data-mode]");
    if (mode) {
      resetLocal();
      send("start:" + mode.getAttribute("data-mode"));
      return;
    }

    if (event.target.closest("[data-details]")) {
      var wrap = event.target.closest(".awd-qz-details");
      var body = wrap && wrap.querySelector(".awd-qz-detail");
      if (body) body.hidden = !body.hidden;
      return;
    }

    var field = event.target.closest("[data-field]");
    if (field) {
      send("field:" + field.getAttribute("data-field"));
      return;
    }
    var auto = event.target.closest("[data-fieldauto]");
    if (auto) {
      send("fieldauto:" + auto.getAttribute("data-fieldauto"));
      return;
    }
    var stepButton = event.target.closest("[data-step-opt]");
    if (stepButton) {
      stepOption(stepButton.getAttribute("data-step-opt"),
                 parseInt(stepButton.getAttribute("data-dir"), 10));
      return;
    }
    var kind = event.target.closest("[data-kind]");
    if (kind) {
      toggleKind(kind.getAttribute("data-kind"));
      return;
    }

    var option = event.target.closest("[data-opt]");
    if (option) {
      /* The pill slides here rather than on the payload that comes back: a
         redraw would rebuild it at the new position with no animation at all,
         and there is nothing on this screen the choice changes but the pill.
         Python only persists it — the same split as the sidebar mode. */
      var seg = option.parentElement;
      if (seg) {
        var buttons = Array.prototype.slice.call(seg.querySelectorAll("button"));
        buttons.forEach(function (button) {
          button.classList.toggle("on", button === option);
        });
        seg.style.setProperty("--awd-seg-i", buttons.indexOf(option));
      }
      send("opt:" + option.getAttribute("data-opt") + ":" + option.getAttribute("data-value"));
      return;
    }

    var tile = event.target.closest("[data-tile]");
    if (tile) {
      onTile(tile);
      return;
    }

    var stepper = event.target.closest("[data-step]");
    if (stepper) {
      step(parseInt(stepper.getAttribute("data-step"), 10));
      return;
    }
    if (event.target.closest("[data-shuffle]")) {
      shuffle();
      return;
    }

    var choice = event.target.closest("[data-choice]");
    if (choice) {
      answer({ index: parseInt(choice.getAttribute("data-choice"), 10) });
      return;
    }
    var tf = event.target.closest("[data-tf]");
    if (tf) {
      answer({ value: tf.getAttribute("data-tf") === "1" });
      return;
    }
    if (event.target.closest("[data-submit]")) {
      submitTyped(false);
      return;
    }
    if (event.target.closest("[data-skip]")) {
      submitTyped(true);
      return;
    }
    if (event.target.closest("[data-hint]")) {
      var hint = document.getElementById("awd-qz-hint");
      if (hint) hint.hidden = false;
      focusInput();
      return;
    }
    if (event.target.closest("#awd-qz-flip") && !onInteractive(event.target)) {
      flipCard();
    }
  }

  function onKey(event) {
    if (!data || !host()) return;
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    var typing =
      event.target &&
      (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA");

    if (data.feedback && showingFeedback) {
      if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        showingFeedback = false;
        data.feedback = null;
        draw();
      }
      return;
    }

    if (typing) {
      if (event.key === "Enter") {
        event.preventDefault();
        submitTyped(false);
      }
      return;
    }

    if (data.screen === "cards") {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        step(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        step(1);
      } else if (event.key === " " || event.key === "Enter") {
        event.preventDefault();
        flipCard();
      }
      return;
    }

    var question = data.question;
    if (!question) return;
    if (question.kind === "tf") {
      if (event.key === "1" || event.key === "ArrowLeft") {
        event.preventDefault();
        answer({ value: true });
      } else if (event.key === "2" || event.key === "ArrowRight") {
        event.preventDefault();
        answer({ value: false });
      }
      return;
    }
    if (question.kind === "choice") {
      var index = parseInt(event.key, 10);
      var options = question.options || [];
      if (index >= 1 && index <= options.length) {
        event.preventDefault();
        answer({ index: index - 1 });
      }
    }
  }

  /* Steps, floors and ceilings live here as well as in screens/quizlet.py,
     which clamps whatever arrives. This copy only has to be right often enough
     that the number on screen does not jump when the answer comes back. */
  var STEPS = {
    sessionSize: { step: 10, min: 0, max: 400 },
    testLength: { step: 5, min: 5, max: 100 },
    matchPairs: { step: 1, min: 2, max: 12 },
  };

  function stepOption(option, direction) {
    var rule = STEPS[option];
    if (!rule || !data.options) return;
    var next = (data.options[option] || 0) + rule.step * direction;
    next = Math.max(rule.min, Math.min(rule.max, next));
    if (next === data.options[option]) return;
    data.options[option] = next;
    send("opt:" + option + ":" + next);
    draw();
  }

  function toggleKind(kind) {
    var kinds = (data.options && data.options.testTypes) || [];
    var next = kinds.indexOf(kind) >= 0
      ? kinds.filter(function (item) { return item !== kind; })
      : kinds.concat([kind]);
    // A test with no kinds has no questions; Python refuses it too.
    if (!next.length) return;
    data.options.testTypes = next;
    send("opt:testTypes:" + next.join(","));
    draw();
  }

  function resetLocal() {
    cards = { index: 0, flipped: false, order: null };
    match = { picked: null, done: 0, start: 0, timer: null, locked: false };
    showingFeedback = false;
  }

  /* ---------- entry points ---------- */

  AwdQz.mount = function () {
    data = window.AWD_QZ || null;
    strings = window.AWD_QZ_I18N || {};
    resetLocal();
    draw();
  };

  AwdQz.apply = function (payload) {
    data = payload;
    showingFeedback = !!(payload && payload.feedback);
    if (payload && payload.screen !== "cards") {
      cards.order = null;
      cards.index = 0;
    }
    draw();
  };

  /* One delegated pair of listeners on the document, bound once. The page is
     rebuilt on every step, so binding per render would stack a new handler on
     each one and answer a question several times over. */
  if (!AwdQz._bound) {
    AwdQz._bound = true;
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);
  }
})();
