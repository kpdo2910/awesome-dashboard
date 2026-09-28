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

  function levelOf(count, scale) {
    if (!count) return 0;
    if (!scale) return 1;
    if (count >= scale * 1.3) return 4;
    if (count >= scale * 0.8) return 3;
    if (count >= scale * 0.4) return 2;
    return 1;
  }

  function levelFor(count, key) {
    return levelOf(count, scaleFor(key));
  }

  /* Future days have no history to scale against, so the booked due load is
     measured against the latest change point — today's own normal. */
  function dueLevelFor(count) {
    var points = data().heatmapScale || [];
    return levelOf(count, points.length ? points[points.length - 1][1] : 0);
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
    // Booked reviews can spill into January of a year with no history yet.
    var forecast = data().forecast || {};
    for (var fkey in forecast) {
      if (forecast[fkey] > 0) {
        var fy = parseInt(fkey.slice(0, 4), 10);
        if (fy) years[fy] = true;
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
    var forecast = data().forecast || {};
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
        var key = dayKey(day);
        if (day > todayDay) {
          var due = forecast[key] || 0;
          return due ? "future due-l" + dueLevelFor(due) : "future";
        }
        return (
          "l" + levelFor(calendar[key] || 0, key) + (day === todayDay ? " today" : "")
        );
      },
    });

    host.innerHTML = "";
    host.appendChild(grid);
    // Current year: the most recent weeks; past years: start at January.
    host.scrollLeft = hmYear === todayYearNum() ? host.scrollWidth : 0;
    bindHeatmap(host);
    renderYearPills();
  }

  /* ---------- tooltip & day click ---------- */

  function formatTooltip(day, dueCount) {
    var months = data().months || [];
    var dayLabel = (data().dayMonthFormat || "{month} {day}")
      .replace("{month}", months[(Math.floor(day / 100) % 100) - 1] || "")
      .replace("{day}", day % 100);
    if (dueCount != null) {
      return dueCount + " " + i18n("cards") + " " + i18n("dueLabel") + " · " + dayLabel;
    }
    var count = (data().calendar || {})[dayKey(day)] || 0;
    return count + " " + i18n("cards") + " · " + dayLabel;
  }

  /* What a cell has to say: reviews done for past days, booked due cards for
     future ones. Padding cells carry no day; an empty future day is nothing. */
  function cellInfo(target) {
    var cell = target.closest(".awd-hm-cell");
    if (!cell || !cell.dataset.day) return null;
    var day = parseInt(cell.dataset.day, 10);
    if (cell.classList.contains("future")) {
      var due = (data().forecast || {})[dayKey(day)] || 0;
      return due ? { day: day, count: due, future: true } : null;
    }
    return {
      day: day,
      count: (data().calendar || {})[dayKey(day)] || 0,
      future: false,
    };
  }

  /* Bound once per page: buildHeatmap only replaces the host's children, so
     binding per build would stack a duplicate set of listeners on every year
     switch — and a click would then open the Browser once per switch. */
  function bindHeatmap(host) {
    if (host.__awdBound) return;
    host.__awdBound = true;
    var tip = document.getElementById("awd-tooltip");

    host.addEventListener("mousemove", function (event) {
      if (!tip) return;
      var info = cellInfo(event.target);
      if (!info) {
        tip.hidden = true;
        return;
      }
      tip.textContent = formatTooltip(info.day, info.future ? info.count : null);
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
      if (tip) tip.hidden = true;
    });

    // A day with something behind it opens the Browser on exactly that day.
    // Python picks the search, so every date rule stays on one side of the
    // bridge; the payload is the day key itself, never an index.
    host.addEventListener("click", function (event) {
      var info = cellInfo(event.target);
      if (!info || !info.count || typeof pycmd !== "function") return;
      pycmd("awd:hm:browse:" + dayKey(info.day));
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

  /* ---------- drag a deck onto another to nest it ----------
     Anki's own protocol: `drag:<deck>,<new parent>` is the native pycmd, an
     empty parent meaning top level, so Python has nothing to add — only the
     gesture is ours. Pointer events rather than HTML5 drag and drop, which
     would hand the gesture to the OS through Qt: this stays in the page, like
     the jQuery UI drag the native screen uses, and holds for the same 200 ms
     before a press becomes a drag, so a click stays a click. */

  var DND_ROWS = ".awd-deck-row, .awd-sd-row";
  var DND_HOLD_MS = 200;
  var DND_MOVE_PX = 4;
  var DND_EDGE_PX = 48;
  var DND_GHOST_MAX = 360;

  var dnd = null;
  var dndSwallowClick = false;

  function dndRow(target) {
    return target && target.closest ? target.closest(DND_ROWS) : null;
  }

  function dndMoved(state) {
    return (
      Math.abs(state.lastX - state.x) + Math.abs(state.lastY - state.y) >=
      DND_MOVE_PX
    );
  }

  document.addEventListener("pointerdown", function (event) {
    if (dnd || event.button !== 0) return;
    if (event.target.closest("button, a, input")) return;
    var row = dndRow(event.target);
    if (!row || !row.dataset.did) return;
    // Measured now, against the same layout the press landed on: by the time
    // the hold elapses the row may have moved (a collapse animation above it).
    var rect = row.getBoundingClientRect();
    var state = {
      pointerId: event.pointerId,
      row: row,
      did: row.dataset.did,
      parent: row.dataset.parent || "0",
      x: event.clientX,
      y: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      width: Math.min(rect.width, DND_GHOST_MAX),
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      armed: false,
      dragging: false,
      descendants: {},
      over: null,
      ghost: null,
      zones: [],
      timer: 0,
      raf: 0,
    };
    // A deck cannot go inside itself. Either list carries the whole tree, so
    // this row's own group names every deck below it.
    var group = row.closest(".awd-deck-group, .awd-sd-group");
    if (group) {
      group.querySelectorAll("[data-did]").forEach(function (el) {
        state.descendants[el.dataset.did] = true;
      });
    }
    state.timer = setTimeout(function () {
      state.armed = true;
      // Already moved while waiting: start now rather than on the next move.
      if (dnd === state && !state.dragging && dndMoved(state)) {
        dndStart(state);
        dndTrack(state);
      }
    }, DND_HOLD_MS);
    dnd = state;
  });

  document.addEventListener("pointermove", function (event) {
    var state = dnd;
    if (!state || event.pointerId !== state.pointerId) return;
    state.lastX = event.clientX;
    state.lastY = event.clientY;
    if (!state.dragging) {
      if (!state.armed || !dndMoved(state)) return;
      dndStart(state);
    }
    dndTrack(state);
  });

  document.addEventListener("pointerup", function (event) {
    if (dnd && event.pointerId === dnd.pointerId) dndFinish(dnd, true);
  });
  document.addEventListener("pointercancel", function (event) {
    if (dnd && event.pointerId === dnd.pointerId) dndFinish(dnd, false);
  });
  window.addEventListener("blur", function () {
    if (dnd) dndFinish(dnd, false);
  });

  // The click that follows a drop would open the deck it landed on. Capture
  // phase, because the rows' handlers are inline onclick attributes.
  document.addEventListener(
    "click",
    function (event) {
      if (!dndSwallowClick) return;
      event.stopPropagation();
      event.preventDefault();
    },
    true
  );

  function dndStart(state) {
    state.dragging = true;
    // The ghost is capped narrower than a full-width row, so a grab near the
    // right end is pulled back under the pointer.
    state.offsetX = Math.max(12, Math.min(state.offsetX, state.width - 24));

    var ghost = state.row.cloneNode(true);
    ghost.classList.add("awd-drag-ghost");
    ghost.classList.remove("awd-drag-source", "awd-drop-hover");
    ghost.removeAttribute("data-did");
    ghost.removeAttribute("onclick");
    ghost.style.width = state.width + "px";
    ghost.style.setProperty("--depth", "0");
    ghost.style.setProperty("--sd", "0");
    // Body level, outside .awd: a transformed ancestor would trap a fixed
    // element inside the card grid.
    document.body.appendChild(ghost);
    state.ghost = ghost;

    state.row.classList.add("awd-drag-source");
    document.documentElement.classList.add("awd-dnd");

    // Only a nested deck has anywhere "up" to go.
    if (state.parent !== "0") {
      [".awd-deck-list", "#awd-side-decks"].forEach(function (selector) {
        var host = document.querySelector(selector);
        if (!host) return;
        var zone = document.createElement("div");
        zone.className =
          "awd-drop-top" + (selector === "#awd-side-decks" ? " sd" : "");
        zone.dataset.drop = "top";
        zone.textContent = i18n("dropTop");
        host.appendChild(zone);
        state.zones.push(zone);
      });
    }

    var tick = function () {
      dndAutoScroll(state);
      state.raf = requestAnimationFrame(tick);
    };
    state.raf = requestAnimationFrame(tick);
  }

  function dndTarget(state) {
    var el = document.elementFromPoint(state.lastX, state.lastY);
    if (!el || !el.closest) return null;
    var top = el.closest('[data-drop="top"]');
    if (top) return state.parent === "0" ? null : top;
    var row = dndRow(el);
    if (!row) return null;
    var did = row.dataset.did;
    if (!did || did === state.parent || state.descendants[did]) return null;
    if (row.dataset.filtered) return null;
    return row;
  }

  function dndTrack(state) {
    state.ghost.style.transform =
      "translate(" + (state.lastX - state.offsetX) + "px," +
      (state.lastY - state.offsetY) + "px)";
    var target = dndTarget(state);
    if (target === state.over) return;
    if (state.over) state.over.classList.remove("awd-drop-hover");
    if (target) target.classList.add("awd-drop-hover");
    state.over = target;
  }

  /* Near the top or bottom edge, scroll whatever is under the pointer: the
     sidebar's own list, or the page. */
  function dndAutoScroll(state) {
    var el = document.elementFromPoint(state.lastX, state.lastY);
    var pane = el && el.closest ? el.closest("#awd-side-decks") : null;
    var top = 0;
    var bottom = window.innerHeight;
    if (pane) {
      var rect = pane.getBoundingClientRect();
      top = rect.top;
      bottom = rect.bottom;
    }
    var step = 0;
    if (state.lastY < top + DND_EDGE_PX) {
      step = -Math.ceil((top + DND_EDGE_PX - state.lastY) / 4);
    } else if (state.lastY > bottom - DND_EDGE_PX) {
      step = Math.ceil((state.lastY - (bottom - DND_EDGE_PX)) / 4);
    }
    if (!step) return;
    step = Math.max(-24, Math.min(24, step));
    if (pane) pane.scrollTop += step;
    else window.scrollBy(0, step);
    dndTrack(state);
  }

  function dndFinish(state, drop) {
    clearTimeout(state.timer);
    dnd = null;
    if (!state.dragging) return;
    cancelAnimationFrame(state.raf);
    var target = drop ? state.over : null;
    if (state.over) state.over.classList.remove("awd-drop-hover");
    state.ghost.remove();
    state.zones.forEach(function (zone) {
      zone.remove();
    });
    state.row.classList.remove("awd-drag-source");
    document.documentElement.classList.remove("awd-dnd");
    dndSwallowClick = true;
    setTimeout(function () {
      dndSwallowClick = false;
    }, 60);
    if (!target || typeof pycmd !== "function") return;
    var parent = target.dataset.drop === "top" ? "" : target.dataset.did;
    Awd.saveScroll();
    pycmd("drag:" + state.did + "," + parent);
  }

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
