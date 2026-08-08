/* ============================================================
   habits.js — the habit strip on the dashboard.
   Reads window.AWD_DATA.habits injected by screens/habits.py.

   A tap repaints its own chip and nothing else. Re-rendering the
   deck browser for a checkbox would drop the scroll position and
   flash the page, so the DOM is updated optimistically and the
   value the store actually wrote comes back through applyValue().
   ============================================================ */

(function () {
  "use strict";

  var AwdHabit = (window.AwdHabit = window.AwdHabit || {});
  var items = [];
  var byId = {};

  function data() {
    return (window.AWD_DATA && window.AWD_DATA.habits) || {};
  }

  function i18n(key) {
    return (data().i18n || {})[key] || "";
  }

  function fill(text, values) {
    return String(text).replace(/\{(\w+)\}/g, function (whole, name) {
      return name in values ? values[name] : whole;
    });
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------- model ----------
     `base` is the streak *without* today counted, so the badge can move the
     moment the chip does. Appending today to a run only ever adds one, and a
     weekly habit's run only moves when the week crosses its target — anything
     subtler than that is the next full render's job. */

  function isComplete(item) {
    return item.count ? item.value >= item.target : item.value > 0;
  }

  function weekComplete(item) {
    return !!item.weekly && item.weekDone >= item.weekTarget;
  }

  /* What the header counts. A weekly habit that has already made its week is
     not an outstanding task today — see stats.day_summary, which counts the
     same way on the Python side. */
  function satisfied(item) {
    return isComplete(item) || weekComplete(item);
  }

  function prepare(list) {
    items = (list || []).map(function (raw) {
      var item = {};
      for (var key in raw) item[key] = raw[key];
      var counted = item.weekly ? weekComplete(item) : item.due && isComplete(item);
      item.base = Math.max(0, item.streak - (counted ? 1 : 0));
      return item;
    });
    byId = {};
    items.forEach(function (item) {
      byId[item.id] = item;
    });
  }

  function streakOf(item) {
    var counted = item.weekly ? weekComplete(item) : item.due && isComplete(item);
    return item.base + (counted ? 1 : 0);
  }

  /* Mirror of HabitStore.toggle. The store stays the authority — this only has
     to agree with it often enough that applyValue() never visibly corrects. */
  function nextValue(item) {
    if (!item.count) return item.value ? 0 : 1;
    if (item.value >= item.target) return 0;
    return Math.min(item.target, item.value + (item.step || 1));
  }

  /* ---------- rendering ---------- */

  function subText(item) {
    if (!item.due) return i18n("offDay");
    if (item.count) {
      return item.value + "/" + item.target + (item.unit ? " " + item.unit : "");
    }
    if (item.weekly) {
      return fill(i18n("thisWeek"), { done: item.weekDone, total: item.weekTarget });
    }
    return "";
  }

  function chipHtml(item) {
    var sub = subText(item);
    // No decrement control. It was absolutely positioned over the tick circle,
    // so hovering a count habit looked like the tick had turned into a minus.
    // Tapping past the target already wraps back to zero.
    return (
      '<span class="awd-hb-ic">' + escapeHtml(item.icon) + "</span>" +
      '<span class="awd-hb-text">' +
      '<span class="awd-hb-name">' + escapeHtml(item.name) + "</span>" +
      '<span class="awd-hb-sub">' + escapeHtml(sub) + "</span>" +
      "</span>" +
      '<span class="awd-hb-streak"></span>' +
      '<span class="awd-hb-check">✓</span>'
    );
  }

  function paintChip(node, item) {
    var complete = isComplete(item);
    var partial = !complete && item.value > 0;
    node.classList.toggle("done", complete);
    node.classList.toggle("partial", partial);
    node.classList.toggle("satisfied", !complete && weekComplete(item));
    node.classList.toggle("off", !item.due);
    node.style.setProperty(
      "--awd-fill",
      item.count && item.target ? (100 * Math.min(1, item.value / item.target)).toFixed(1) + "%" : "0%"
    );
    var sub = node.querySelector(".awd-hb-sub");
    if (sub) sub.textContent = subText(item);
    // Just the number: the unit costs more width than a chip can spare, and
    // spending it here is what pushes the habit's own name into an ellipsis.
    var run = streakOf(item);
    var unit = item.weekly ? i18n("weeks") : i18n("days");
    var streak = node.querySelector(".awd-hb-streak");
    if (streak) streak.textContent = run ? "🔥 " + run : "";

    var title = item.name;
    if (run) title += " · 🔥 " + run + " " + unit;
    if (item.weekly) {
      title += " · " + fill(i18n("thisWeek"), {
        done: item.weekDone,
        total: item.weekTarget,
      });
    }
    node.title = title;
  }

  function paintHeader() {
    var due = 0;
    var done = 0;
    items.forEach(function (item) {
      if (!item.due) return;
      due += 1;
      if (satisfied(item)) done += 1;
    });
    var label = document.getElementById("awd-hb-count");
    if (label) {
      label.classList.toggle("all-done", due > 0 && done === due);
      // Escape the template first, then substitute — the placeholders take
      // numbers and the <b> is ours, so nothing user-supplied reaches innerHTML.
      label.innerHTML =
        due === 0
          ? ""
          : done === due
            ? escapeHtml(i18n("allDone"))
            : fill(escapeHtml(i18n("done")), {
                done: "<b>" + done + "</b>",
                total: due,
              });
    }
    var bar = document.getElementById("awd-hb-fill");
    if (bar) bar.style.width = due ? (100 * done / due).toFixed(1) + "%" : "0%";
  }

  function render() {
    var host = document.getElementById("awd-hb-grid");
    if (!host) return;
    host.innerHTML = "";
    items.forEach(function (item) {
      var chip = document.createElement("button");
      chip.className = "awd-hb";
      chip.dataset.id = item.id;
      chip.style.setProperty("--awd-tint", item.color);
      chip.innerHTML = chipHtml(item);
      chip.addEventListener("click", function (event) {
        AwdHabit.tick(event, item.id);
      });
      host.appendChild(chip);
      paintChip(chip, item);
    });
    var card = host.closest(".awd-hb-card");
    var empty = document.getElementById("awd-hb-empty");
    if (empty) empty.hidden = items.length > 0;
    if (card) card.dataset.empty = items.length ? "0" : "1";
    paintHeader();
  }

  function nodeFor(id) {
    return document.querySelector('.awd-hb[data-id="' + id + '"]');
  }

  function commit(item, value) {
    var was = isComplete(item);
    item.value = value;
    var now = isComplete(item);
    // Only a change of state moves the week's tally: stepping a count habit
    // from 1 to 2 out of 3 is not another repetition.
    if (item.weekly && now !== was) {
      item.weekDone = Math.max(0, (item.weekDone || 0) + (now ? 1 : -1));
    }
    var node = nodeFor(item.id);
    if (node) paintChip(node, item);
    paintHeader();
  }

  /* ---------- commands ---------- */

  AwdHabit.tick = function (event, id) {
    if (event) event.stopPropagation();
    var item = byId[id];
    if (!item) return;
    commit(item, nextValue(item));
    if (typeof pycmd === "function") pycmd("awd:habit:toggle:" + id);
  };

  /* What the store actually wrote. Normally identical to the optimistic value;
     when it is not, this is the correction. */
  AwdHabit.applyValue = function (payload) {
    var item = payload && byId[payload.id];
    if (!item || item.value === payload.value) return;
    commit(item, payload.value);
  };

  /* ---------- init ---------- */

  function init() {
    if (!document.getElementById("awd-hb-grid")) return;
    prepare(data().items);
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
