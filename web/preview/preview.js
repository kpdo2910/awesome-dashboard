/* ============================================================
   preview.js — draws the cards preview grid. Every number
   arrives from screens/preview.py: which cards are on this
   page, how many pages there are, and what the toolbar's
   controls are currently set to. This file only draws them.

   The exceptions are deliberate and both are animation:
   turning one tile over, and "flip all". A payload that
   redrew the grid would rebuild every tile already at its
   destination and the flip would never run. Python is told
   about the *options*, because those are persisted; it is
   never asked to turn a card over.
   ============================================================ */

(function () {
  "use strict";

  var AwdCp = (window.AwdCp = window.AwdCp || {});

  var data = null;
  var strings = {};

  /* Client-side and not authoritative: which tiles are showing their back.
     Keyed by card id, so a redraw that keeps a card keeps its side. A card
     with no entry follows `allFlipped`, which is how tiles arriving on a
     later page still obey a "flip all" that is still switched on. */
  var flipped = {};
  var allFlipped = false;
  var mathLoading = false;

  function host() {
    return document.getElementById("awd-cp");
  }

  function send(command) {
    if (typeof pycmd === "function") pycmd("awd:cp:" + command);
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

  function icon(paths, extra) {
    return (
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true"' + (extra || "") + ">" + paths + "</svg>"
    );
  }

  /* ---------- toolbar ---------- */

  function option(value, label, current) {
    return (
      '<option value="' + escapeHtml(value) + '"' +
      (String(value) === String(current) ? " selected" : "") +
      ">" + escapeHtml(label) + "</option>"
    );
  }

  function select(name, label, options, current) {
    var items = options
      .map(function (entry) {
        return option(entry[0], entry[1], current);
      })
      .join("");
    return (
      '<label class="awd-cp-field"><span>' + escapeHtml(label) + "</span>" +
      '<select data-opt="' + name + '">' + items + "</select></label>"
    );
  }

  function numbers(values) {
    return values.map(function (n) {
      return [n, String(n)];
    });
  }

  function toolbar() {
    var options = data.options;
    return (
      '<div class="awd-cp-bar">' +
      select("columns", i18n("cp_columns"), numbers(data.columns), options.columns) +
      select("rows", i18n("cp_rows"), numbers(data.rows), options.rows) +
      select("ratio", i18n("cp_ratio"),
             data.ratios.map(function (r) { return [r, r]; }), options.ratio) +
      select("sort", i18n("cp_sort"), [
        ["added", i18n("cp_sort_added")],
        ["due", i18n("cp_sort_due")],
        ["alpha", i18n("cp_sort_alpha")],
      ], options.sort) +
      select("flip", i18n("cp_flip_mode"), [
        ["click", i18n("cp_flip_click")],
        ["hover", i18n("cp_flip_hover")],
      ], options.flip) +
      '<label class="awd-cp-field"><span>' + escapeHtml(i18n("cp_font")) + "</span>" +
      '<input type="range" data-opt="font" min="70" max="160" step="10" value="' +
      Number(options.font) + '"></label>' +
      '<button class="awd-cp-flipall' + (allFlipped ? " on" : "") + '" data-flipall>' +
      icon('<path d="M3 12a9 9 0 0 1 15.3-6.4L21 8"/><path d="M21 3v5h-5"/>' +
           '<path d="M21 12a9 9 0 0 1-15.3 6.4L3 16"/><path d="M3 21v-5h5"/>') +
      "<span>" + escapeHtml(i18n(allFlipped ? "cp_unflip_all" : "cp_flip_all")) +
      "</span></button></div>"
    );
  }

  /* ---------- tiles ---------- */

  function faceHtml(markup, blank, label) {
    var body = blank
      ? '<div class="awd-cp-blank">' + escapeHtml(i18n("cp_blank")) + "</div>"
      : markup;
    return body + '<span class="awd-cp-side">' + escapeHtml(label) + "</span>";
  }

  function isFlipped(id) {
    return Object.prototype.hasOwnProperty.call(flipped, id)
      ? flipped[id]
      : allFlipped;
  }

  function tile(card) {
    var flag = card.flag
      ? '<span class="awd-cp-flag f' + card.flag + '"></span>'
      : "";
    return (
      '<div class="awd-cp-tile' + (isFlipped(card.id) ? " flipped" : "") +
      '" data-id="' + card.id + '">' +
      '<span class="awd-cp-state ' + escapeHtml(card.state) + '" title="' +
      escapeHtml(i18n("cp_state_" + card.state)) + '"></span>' + flag +
      '<div class="awd-cp-inner">' +
      '<div class="awd-cp-face front">' +
      faceHtml(card.front, card.frontBlank, i18n("cp_side_front")) +
      "</div>" +
      '<div class="awd-cp-face back">' +
      faceHtml(card.back, card.backBlank, i18n("cp_side_back")) +
      "</div></div></div>"
    );
  }

  function grid() {
    if (!data.cards.length) {
      return (
        '<div class="awd-cp-empty">' +
        '<div class="awd-cp-empty-title">' + escapeHtml(i18n("cp_empty_title")) +
        "</div>" +
        '<div class="awd-cp-empty-body">' + escapeHtml(i18n("cp_empty_body")) +
        "</div></div>"
      );
    }
    return '<div class="awd-cp-grid">' + data.cards.map(tile).join("") + "</div>";
  }

  function pager() {
    if (data.pages < 2) return "";
    var first = data.page === 0;
    var last = data.page >= data.pages - 1;
    return (
      '<div class="awd-cp-pager">' +
      '<button data-page="' + (data.page - 1) + '"' + (first ? " disabled" : "") +
      ' title="' + escapeHtml(i18n("cp_prev")) + '">' +
      icon('<path d="M15 5.5 8.5 12l6.5 6.5"/>') + "</button>" +
      '<span class="awd-cp-pager-label">' +
      escapeHtml(i18n("cp_page", { page: data.page + 1, pages: data.pages })) +
      "</span>" +
      '<button data-page="' + (data.page + 1) + '"' + (last ? " disabled" : "") +
      ' title="' + escapeHtml(i18n("cp_next")) + '">' +
      icon('<path d="m9 5.5 6.5 6.5L9 18.5"/>') + "</button></div>"
    );
  }

  function header() {
    return (
      '<div class="awd-cp-head">' +
      '<span class="awd-cp-back" data-close>' +
      icon('<path d="M15 5.5 8.5 12l6.5 6.5"/>') +
      "<span>" + escapeHtml(i18n("qz_back")) + "</span></span>" +
      '<h1 class="awd-cp-title">' + escapeHtml(data.deck) + "</h1>" +
      '<span class="awd-cp-count">' +
      escapeHtml(i18n("cp_cards", { n: data.total })) + "</span></div>"
    );
  }

  /* ---------- MathJax ----------
     Anki's own bundle, loaded only when a tile actually carries TeX: it is
     1.3MB, and an ordinary deck should never pay for it. The two scripts and
     their order are the reviewer's (aqt/reviewer.py `_initWeb`) — the first
     one is the configuration the second reads on startup. */

  function typeset() {
    var node = host();
    if (!node || !window.MathJax || !MathJax.startup) return;
    MathJax.startup.promise
      .then(function () {
        MathJax.typesetClear();
        return MathJax.typesetPromise([node]);
      })
      .catch(function (error) {
        console.log("[Awesome Dashboard] preview: MathJax failed", error);
      });
  }

  function withMath() {
    if (window.MathJax) return typeset();
    if (mathLoading) return;
    mathLoading = true;
    var sources = [
      "/_anki/js/mathjax.js",
      "/_anki/js/vendor/mathjax/tex-chtml-full.js",
    ];
    (function next(index) {
      if (index >= sources.length) return typeset();
      var script = document.createElement("script");
      script.src = sources[index];
      script.onload = function () {
        next(index + 1);
      };
      script.onerror = function () {
        console.log("[Awesome Dashboard] preview: cannot load " + sources[index]);
      };
      document.head.appendChild(script);
    })(0);
  }

  /* ---------- drawing ---------- */

  function draw() {
    var node = host();
    if (!node || !data) return;
    node.style.setProperty("--awd-cp-cols", String(data.options.columns));
    node.style.setProperty("--awd-cp-aspect", data.aspect);
    node.style.setProperty("--awd-cp-font",
                           String(Number(data.options.font) / 100));
    node.classList.toggle("hoverflip", data.options.flip === "hover");
    node.innerHTML = header() + toolbar() + grid() + pager();
    if (data.math) withMath();
  }

  function setFlipped(tileNode, on) {
    flipped[tileNode.getAttribute("data-id")] = on;
    tileNode.classList.toggle("flipped", on);
  }

  /* ---------- events ----------
     Bound once on the host, not per tile: `draw` replaces the host's children
     on every payload, so per-tile binding would stack handlers and one click
     would eventually flip a card several times over. */

  function onClick(event) {
    var node = host();
    if (!node) return;

    var close = event.target.closest(".awd-cp-back");
    if (close && node.contains(close)) return send("close");

    var page = event.target.closest("[data-page]");
    if (page && node.contains(page)) {
      if (page.disabled) return;
      return send("page:" + page.getAttribute("data-page"));
    }

    var flipAll = event.target.closest("[data-flipall]");
    if (flipAll && node.contains(flipAll)) {
      allFlipped = !allFlipped;
      flipped = {};
      Array.prototype.forEach.call(
        node.querySelectorAll(".awd-cp-tile"),
        function (tileNode) {
          tileNode.classList.toggle("flipped", allFlipped);
        }
      );
      flipAll.classList.toggle("on", allFlipped);
      var label = flipAll.querySelector("span");
      if (label) {
        label.textContent = i18n(allFlipped ? "cp_unflip_all" : "cp_flip_all");
      }
      return;
    }

    // A play button inside a face has its own pycmd; leave it alone rather
    // than also turning the card over under the user's finger.
    if (event.target.closest(".awd-skin-audio")) return;

    var tileNode = event.target.closest(".awd-cp-tile");
    if (tileNode && node.contains(tileNode) && data.options.flip === "click") {
      setFlipped(tileNode, !tileNode.classList.contains("flipped"));
    }
  }

  function onOver(event) {
    if (!data || data.options.flip !== "hover") return;
    var node = host();
    var tileNode = event.target.closest && event.target.closest(".awd-cp-tile");
    if (!tileNode || !node || !node.contains(tileNode)) return;
    setFlipped(tileNode, true);
  }

  function onOut(event) {
    if (!data || data.options.flip !== "hover") return;
    var tileNode = event.target.closest && event.target.closest(".awd-cp-tile");
    if (!tileNode) return;
    // `relatedTarget` is where the pointer went; still inside the tile means
    // it only crossed between the tile's own children.
    if (tileNode.contains(event.relatedTarget)) return;
    setFlipped(tileNode, allFlipped);
  }

  function onChange(event) {
    var control = event.target.closest("[data-opt]");
    if (!control) return;
    send("opt:" + control.getAttribute("data-opt") + ":" + control.value);
  }

  function onInput(event) {
    var control = event.target.closest('[data-opt="font"]');
    if (!control) return;
    // The drag is answered here and persisted on release: a pycmd per step
    // would be a round trip per pixel, and the payload it returned would
    // redraw the grid under the handle.
    var node = host();
    if (node) {
      node.style.setProperty("--awd-cp-font",
                             String(Number(control.value) / 100));
    }
  }

  function onKey(event) {
    if (!data || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === "ArrowLeft" && data.page > 0) {
      event.preventDefault();
      send("page:" + (data.page - 1));
    } else if (event.key === "ArrowRight" && data.page < data.pages - 1) {
      event.preventDefault();
      send("page:" + (data.page + 1));
    } else if (event.key === "Escape") {
      event.preventDefault();
      send("close");
    }
  }

  var bound = false;

  function bind() {
    if (bound) return;
    bound = true;
    document.addEventListener("click", onClick);
    document.addEventListener("mouseover", onOver);
    document.addEventListener("mouseout", onOut);
    document.addEventListener("change", onChange);
    document.addEventListener("input", onInput);
    document.addEventListener("keydown", onKey);
  }

  AwdCp.mount = function () {
    data = window.AWD_CP || null;
    strings = window.AWD_CP_I18N || {};
    flipped = {};
    allFlipped = false;
    bind();
    draw();
  };

  AwdCp.apply = function (payload) {
    var samePage = data && payload.page === data.page &&
      payload.options.sort === data.options.sort;
    data = payload;
    // A different set of cards means the remembered flips belong to tiles that
    // are no longer here.
    if (!samePage) {
      flipped = {};
      allFlipped = false;
    }
    draw();
  };
})();
