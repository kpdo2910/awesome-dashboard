/* ============================================================
   onboarding.js — drives the first-run overlay.

   Choices are held here until "Apply", then sent in one go. The page is only
   allowed to re-render at the very end, because re-rendering replaces the
   whole document and would take the overlay with it.
   ============================================================ */

(function () {
  "use strict";

  var AwdOb = (window.AwdOb = window.AwdOb || {});
  var STEPS = 7;
  var LAST_CHOICE_STEP = 4;

  var picked = {};
  var current = 0;

  function root() {
    return document.getElementById("awd-ob");
  }

  function send(message) {
    if (typeof pycmd === "function") pycmd(message);
  }

  function section(step) {
    var host = root();
    return host ? host.querySelector('.awd-ob-step[data-step="' + step + '"]') : null;
  }

  function clearMotion(node) {
    node.classList.remove("enter-next", "enter-prev", "leave-next", "leave-prev");
  }

  function enter(node, direction) {
    clearMotion(node);
    node.hidden = false;
    // Re-adding the class alone will not replay an animation that already ran.
    void node.offsetWidth;
    node.classList.add("enter-" + direction);
  }

  function show(step) {
    var host = root();
    if (!host) return;
    var incoming = section(step);
    var outgoing = section(current);
    var direction = step >= current ? "next" : "prev";
    current = step;
    updateDots();
    if (!incoming) return;

    if (!outgoing || outgoing === incoming || outgoing.hidden) {
      enter(incoming, direction);
      return;
    }
    clearMotion(outgoing);
    void outgoing.offsetWidth;
    outgoing.classList.add("leave-" + direction);
    setTimeout(function () {
      outgoing.hidden = true;
      clearMotion(outgoing);
      enter(incoming, direction);
    }, 150);
  }

  function updateTopBar() {
    var bar = document.getElementById("awd-ob-top");
    var sheet = document.getElementById("awd-ob-sheet");
    // Intro has its own Skip, and the outcome screens have nothing to go back to.
    var wanted = current > 0 && current <= LAST_CHOICE_STEP;
    if (bar) bar.hidden = !wanted;
    if (sheet) sheet.classList.toggle("with-top", wanted);
  }

  function buildDots() {
    var dots = document.getElementById("awd-ob-dots");
    if (!dots) return;
    var out = "";
    for (var i = 0; i <= LAST_CHOICE_STEP; i++) out += "<i></i>";
    dots.innerHTML = out;
  }

  function updateDots() {
    var dots = document.getElementById("awd-ob-dots");
    if (!dots) return;
    // Applying and finished are outcomes, not steps to navigate between.
    dots.classList.toggle("gone", current > LAST_CHOICE_STEP);
    updateTopBar();
    var items = dots.children;
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle("on", i === current);
      items[i].classList.toggle("done", i < current);
    }
  }

  /* ---------- live preview ----------
     Every palette rides along in AWD_DATA, so a pick repaints the overlay
     itself rather than describing a change the user only sees at the end.
     AwdTheme.apply cross-fades, which is why nothing has to be re-rendered. */

  function onboardData() {
    return (window.AWD_DATA || {}).onboard || {};
  }

  function previewPalette() {
    var info = onboardData();
    var palettes = info.palettes || {};
    if (!window.AwdTheme || !palettes) return;

    var theme = picked.theme || info.theme;
    if (!palettes[theme]) return;

    var night = info.night;
    if (picked.appearance === "light") night = false;
    else if (picked.appearance === "dark") night = true;

    window.AwdTheme.apply(palettes[theme][night ? "dark" : "light"]);
    if (window.AwdTheme.setNightMode) window.AwdTheme.setNightMode(night);
  }

  function markPicked(button) {
    var choice = button.dataset.choice;
    picked[choice] = button.dataset.value;
    var siblings = root().querySelectorAll(
      '.awd-ob-opt[data-choice="' + choice + '"]'
    );
    for (var i = 0; i < siblings.length; i++) {
      siblings[i].classList.toggle("picked", siblings[i] === button);
    }
    if (choice === "theme" || choice === "appearance") previewPalette();
  }

  function apply() {
    show(5);
    send("awd:onboard:apply:" + JSON.stringify(picked));
    // Python does its work on the main thread while this screen is up; the
    // delay is what makes the step readable rather than a flash.
    setTimeout(function () {
      show(6);
    }, 1100);
  }

  function finish() {
    // Only now may the page be rebuilt, with the chosen settings in place.
    send("awd:onboard:finish");
  }

  function preselect() {
    // The page arrives with a theme already applied; showing it as chosen keeps
    // the step honest and means Continue without touching anything is a no-op.
    var current = onboardData().theme;
    if (!current) return;
    var button = root().querySelector(
      '.awd-ob-opt[data-choice="theme"][data-value="' + current + '"]'
    );
    if (button) markPicked(button);
  }

  AwdOb.start = function () {
    var host = root();
    if (!host) return;
    host.hidden = false;

    host.addEventListener("click", function (event) {
      var option = event.target.closest(".awd-ob-opt");
      if (option) {
        markPicked(option);
        return;
      }
      var button = event.target.closest("button");
      if (!button) return;
      if (button.dataset.back !== undefined) show(Math.max(0, current - 1));
      else if (button.dataset.go !== undefined) show(Number(button.dataset.go));
      else if (button.dataset.apply !== undefined) apply();
      else if (button.dataset.finish !== undefined) finish();
      else if (button.dataset.skip !== undefined) finish();
    });

    buildDots();
    preselect();
    show(0);
  };

  AwdOb.STEPS = STEPS;

  // Loaded in <head>, so the overlay may not exist yet.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", AwdOb.start);
  } else {
    AwdOb.start();
  }
})();
