/* ============================================================
   dashboard.js — dashboard behaviour
   Reads window.AWD_DATA injected by the Python renderer:
   heatmap render, custom tooltip, Pomodoro view,
   scroll restore across collapse re-renders.
   ============================================================ */

(function () {
  "use strict";

  var Awd = (window.Awd = window.Awd || {});
  var RING_LENGTH = 326.7; // 2 * PI * r(52)

  function data() {
    return window.AWD_DATA || {};
  }

  function i18n(key) {
    var table = data().i18n || {};
    return table[key] || key;
  }

  /* ---------- deck collapse (client-side, no page re-render) ----------
     The same deck can appear both in the main list and in the sidebar,
     so a toggle applies the new state to every rendered copy. */

  function applyDeckClosed(did, closed) {
    var rows = document.querySelectorAll(
      '.awd-deck-row[data-did="' + did + '"], .awd-sd-row[data-did="' + did + '"]'
    );
    rows.forEach(function (row) {
      var group = row.closest(".awd-deck-group, .awd-sd-group");
      if (!group) return;
      var caret = row.querySelector(".awd-caret, .awd-sd-caret");
      for (var i = 0; i < group.children.length; i++) {
        var child = group.children[i];
        if (
          child.classList.contains("awd-deck-children") ||
          child.classList.contains("awd-sd-children")
        ) {
          child.classList.toggle("closed", closed);
        }
      }
      if (caret) caret.classList.toggle("closed", closed);
    });
  }

  Awd.toggleDeck = function (event, did) {
    event.stopPropagation();
    var closed = !event.currentTarget.classList.contains("closed");
    applyDeckClosed(did, closed);
    if (typeof pycmd === "function") {
      pycmd("awd:collapse:" + did + ":" + (closed ? "1" : "0"));
    }
  };

  /* ---------- sidebar (full / compact / hidden, no page re-render) ---------- */

  function shell() {
    return document.getElementById("awd-shell");
  }

  Awd.sideMode = function (mode) {
    var host = shell();
    if (!host) return;
    host.classList.remove("mode-full", "mode-compact", "mode-hidden");
    host.classList.add("mode-" + mode);
    if (typeof pycmd === "function") pycmd("awd:sidebar:" + mode);
  };

  /* Full <-> compact only. Hiding the sidebar is a Settings choice, so the
     toggle can never strand the user without a way back. */
  Awd.sideToggle = function () {
    var host = shell();
    if (!host) return;
    Awd.sideMode(host.classList.contains("mode-full") ? "compact" : "full");
  };

  Awd.sideFilter = function (query) {
    var host = document.getElementById("awd-side-decks");
    if (!host) return;
    var q = (query || "").trim().toLowerCase();
    host.classList.toggle("filtering", !!q);

    function walk(group, ancestorHit) {
      var selfHit = !!q && (group.dataset.name || "").indexOf(q) !== -1;
      var childHit = false;
      var inner = group.querySelector(
        ":scope > .awd-sd-children > .awd-sd-children-inner"
      );
      if (inner) {
        for (var i = 0; i < inner.children.length; i++) {
          if (walk(inner.children[i], ancestorHit || selfHit)) childHit = true;
        }
      }
      var visible = !q || selfHit || childHit || ancestorHit;
      group.classList.toggle("filter-hide", !visible);
      return selfHit || childHit;
    }

    for (var i = 0; i < host.children.length; i++) {
      if (host.children[i].classList.contains("awd-sd-group")) {
        walk(host.children[i], false);
      }
    }
  };

  /* ---------- scroll persistence across full re-renders ---------- */

  Awd.saveScroll = function () {
    try {
      sessionStorage.setItem("awdScroll", String(window.scrollY || 0));
    } catch (e) {}
  };

  function restoreScroll() {
    try {
      var saved = sessionStorage.getItem("awdScroll");
      if (saved !== null) {
        window.scrollTo(0, parseInt(saved, 10) || 0);
      }
    } catch (e) {}
  }

  var scrollSaveQueued = false;
  window.addEventListener(
    "scroll",
    function () {
      if (scrollSaveQueued) return;
      scrollSaveQueued = true;
      requestAnimationFrame(function () {
        scrollSaveQueued = false;
        Awd.saveScroll();
      });
    },
    { passive: true }
  );

  /* ---------- heatmap ---------- */

  /* The shade is relative to what a normal day looked like at the time, not to
     a fixed number of reviews — see core/heatmap_scale.py. Change points are
     sorted, so the day's scale is the last one at or before it. */

  function scaleFor(key) {
    var points = data().heatmapScale || [];
    var value = 0;
    for (var i = 0; i < points.length; i++) {
      if (points[i][0] > key) break;
      value = points[i][1];
    }
    return value;
  }

  function levelFor(count, key) {
    if (!count) return 0;
    var scale = scaleFor(key);
    if (!scale) return 1;
    if (count >= scale * 1.3) return 4;
    if (count >= scale * 0.8) return 3;
    if (count >= scale * 0.4) return 2;
    return 1;
  }

  /* GitHub-style: one full year at a time, with a year picker. */

  var hmYear = null;

  function todayYearNum() {
    var key = data().todayKey || "";
    return parseInt(key.slice(0, 4), 10) || new Date().getFullYear();
  }

  function yearsAvailable() {
    var years = {};
    years[todayYearNum()] = true;
    var calendar = data().calendar || {};
    for (var key in calendar) {
      if (calendar[key] > 0) {
        var y = parseInt(key.slice(0, 4), 10);
        if (y) years[y] = true;
      }
    }
    return Object.keys(years)
      .map(Number)
      .sort(function (a, b) {
        return a - b;
      });
  }

  function renderYearPills() {
    var host = document.getElementById("awd-hm-years");
    if (!host) return;
    host.innerHTML = "";
    yearsAvailable().forEach(function (year) {
      var pill = document.createElement("button");
      pill.className = "awd-hm-year" + (year === hmYear ? " active" : "");
      pill.textContent = year;
      pill.addEventListener("click", function () {
        if (hmYear !== year) {
          hmYear = year;
          buildHeatmap();
        }
      });
      host.appendChild(pill);
    });
  }

  /* Days are "YYYY-MM-DD" in the calendar bundle but YYYYMMDD integers in the
     shared grid builder, which is the add-on's convention everywhere else. */

  function dayKey(day) {
    var text = String(day);
    return text.slice(0, 4) + "-" + text.slice(4, 6) + "-" + text.slice(6, 8);
  }

  function buildHeatmap() {
    var host = document.getElementById("awd-heatmap");
    if (!host || !data().showHeatmap || !window.AwdHeatmap) return;
    if (hmYear === null) hmYear = todayYearNum();

    var calendar = data().calendar || {};
    var todayKey = data().todayKey || "";
    var todayDay = parseInt(todayKey.replace(/-/g, ""), 10) || 0;

    // The grid itself comes from web/shared/heatmap.js — the habit report's
    // year view draws from the same builder. Only the shading is ours.
    var grid = AwdHeatmap.grid({
      first: hmYear * 10000 + 101,
      last: hmYear * 10000 + 1231,
      firstDay: 1,
      months: data().months || [],
      weekdayLabels: ["", i18n("mon"), "", i18n("wed"), "", i18n("fri"), ""],
      classFor: function (day) {
        if (day > todayDay) return "future";
        var key = dayKey(day);
        return (
          "l" + levelFor(calendar[key] || 0, key) + (day === todayDay ? " today" : "")
        );
      },
    });

    host.innerHTML = "";
    host.appendChild(grid);
    // Current year: the most recent weeks; past years: start at January.
    host.scrollLeft = hmYear === todayYearNum() ? host.scrollWidth : 0;
    bindTooltip(host);
    renderYearPills();
  }

  /* ---------- tooltip ---------- */

  function formatTooltip(day) {
    var key = dayKey(day);
    var count = (data().calendar || {})[key] || 0;
    var months = data().months || [];
    var dayLabel = (data().dayMonthFormat || "{month} {day}")
      .replace("{month}", months[(Math.floor(day / 100) % 100) - 1] || "")
      .replace("{day}", day % 100);
    return count + " " + i18n("cards") + " · " + dayLabel;
  }

  function bindTooltip(host) {
    var tip = document.getElementById("awd-tooltip");
    if (!tip) return;
    host.addEventListener("mousemove", function (event) {
      var cell = event.target.closest(".awd-hm-cell");
      // Padding cells carry no day at all; future ones have nothing to report.
      if (!cell || !cell.dataset.day || cell.classList.contains("future")) {
        tip.hidden = true;
        return;
      }
      tip.textContent = formatTooltip(parseInt(cell.dataset.day, 10));
      tip.hidden = false;
      var x = event.clientX + 12;
      var y = event.clientY - 30;
      if (x + tip.offsetWidth > window.innerWidth - 8) {
        x = event.clientX - tip.offsetWidth - 12;
      }
      tip.style.left = x + "px";
      tip.style.top = Math.max(4, y) + "px";
    });
    host.addEventListener("mouseleave", function () {
      tip.hidden = true;
    });
  }

  /* ---------- pomodoro ---------- */

  function two(n) {
    return n < 10 ? "0" + n : String(n);
  }

  Awd.pomRender = function (state) {
    var timeEl = document.getElementById("awd-pom-time");
    if (!timeEl) return;
    var phaseEl = document.getElementById("awd-pom-phase");
    var ringEl = document.getElementById("awd-pom-ring");
    var toggleEl = document.getElementById("awd-pom-toggle");
    var skipEl = document.getElementById("awd-pom-skip");
    var sessionsEl = document.getElementById("awd-pom-sessions");

    var idle = state.phase === "idle";
    var seconds = idle ? (state.focusMin || 25) * 60 : state.remaining;
    timeEl.textContent = two(Math.floor(seconds / 60)) + ":" + two(seconds % 60);

    if (phaseEl) {
      phaseEl.textContent = idle
        ? i18n("idle")
        : state.phase === "focus"
          ? i18n("focus")
          : i18n("break");
    }

    if (ringEl) {
      var fraction = idle || !state.total ? 0 : state.remaining / state.total;
      ringEl.style.strokeDashoffset = (RING_LENGTH * (1 - fraction)).toFixed(1);
    }

    if (toggleEl) {
      toggleEl.textContent = idle
        ? i18n("start")
        : state.paused
          ? i18n("resume")
          : i18n("pause");
    }
    if (skipEl) skipEl.hidden = idle;

    if (sessionsEl) {
      if (state.sessions > 0) {
        var dots = "🍅".repeat(Math.min(state.sessions, 6));
        var extra = state.sessions > 6 ? " ×" + state.sessions : "";
        sessionsEl.textContent = dots + extra + " · " + i18n("sessions");
      } else {
        sessionsEl.textContent = "";
      }
    }
  };

  /* ---------- init ---------- */

  function init() {
    if (!document.getElementById("awd-root")) return;
    restoreScroll();
    buildHeatmap();
    if (data().showPomodoro && data().pom) Awd.pomRender(data().pom);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
