/* ============================================================
   report.js — draws the habit report, as an overlay over the
   dashboard rather than in a webview of its own. See
   screens/habit_report.py for why.

   Every date and every number arrives from ui/habit_report.py.
   This file only turns them into a grid: the moment it starts
   deciding what counts as "due", the report and the dashboard
   can disagree, and there is no way to tell which is right.

   A period is one character per day (see habit_report.py):
     2 done · 1 partial · 0 missed · - not scheduled
     f future · x outside the habit's life
   ============================================================ */

(function () {
  "use strict";

  var AwdRep = (window.AwdRep = window.AwdRep || {});
  var state = null;

  var CELL_CLASS = {
    "2": "full",
    "1": "part",
    "0": "due",
    "-": "off",
    f: "future",
    x: "off",
  };

  /* Navigation is a local round trip, so the spinner only appears if the answer
     is actually slow. Showing it immediately would flash on every click, which
     reads as the page breaking rather than working. */
  var BUSY_DELAY = 150;
  var busyTimer = null;

  function send(command) {
    if (typeof pycmd !== "function") return;
    clearTimeout(busyTimer);
    busyTimer = setTimeout(showBusy, BUSY_DELAY);
    pycmd("awd:habit:report:" + command);
  }

  function host() {
    return document.getElementById("awd-rep");
  }

  function overlay() {
    return document.getElementById("awd-rep-overlay");
  }

  function showBusy() {
    var where = host();
    if (!where) return;
    where.innerHTML =
      '<div class="awd-loading-pane">' +
      '<div class="awd-spinner" aria-hidden="true"><i></i><i></i><i></i></div>' +
      '<p class="awd-loading">' + escapeHtml(i18n("loading")) + "</p></div>";
  }

  function i18n(key) {
    return ((state && state.i18n) || {})[key] || "";
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function pct(value) {
    return Math.round((value || 0) * 100) + "%";
  }

  /* ---------- day maths on YYYYMMDD integers ---------- */

  function toDate(day) {
    // Midday, so a daylight-saving shift cannot roll the date over.
    return new Date(Math.floor(day / 10000), (Math.floor(day / 100) % 100) - 1,
                    day % 100, 12);
  }

  function fromDate(date) {
    return date.getFullYear() * 10000 + (date.getMonth() + 1) * 100 + date.getDate();
  }

  function dayAt(start, index) {
    var date = toDate(start);
    date.setDate(date.getDate() + index);
    return fromDate(date);
  }

  function isoWeekday(day) {
    return toDate(day).getDay() || 7;
  }

  function leadingBlanks(start) {
    return (isoWeekday(start) - state.firstDay + 7) % 7;
  }

  function dateLabel(day) {
    var date = toDate(day);
    return date.getDate() + " " + (state.months[date.getMonth()] || "");
  }

  /* ---------- cells ---------- */

  function cellTitle(habit, day) {
    var label = dateLabel(day);
    var values = habit.values;
    if (!values) return label;
    var value = values[String(day)] || 0;
    if (!habit.count) return label;
    return label + " · " + value + "/" + habit.target + (habit.unit ? " " + habit.unit : "");
  }

  function cell(habit, index) {
    var char = habit.levels.charAt(index) || "-";
    var day = dayAt(state.first, index);
    var classes = ["awd-cell", CELL_CLASS[char] || "off"];
    // Not on a day the habit did not exist for: an empty ring on an archived
    // row reads as something that was expected and missed.
    if (day === state.today && char !== "x") classes.push("today");
    return (
      '<span class="' + classes.join(" ") + '" title="' +
      escapeHtml(cellTitle(habit, day)) + '"></span>'
    );
  }

  function tint(habit) {
    return ' style="--awd-tint:' + escapeHtml(habit.color) + '"';
  }

  function habitName(habit) {
    var tag = habit.archived ? " (" + escapeHtml(i18n("archived")) + ")" : "";
    return '<span class="ic">' + escapeHtml(habit.icon) + "</span>" +
           escapeHtml(habit.name) + tag;
  }

  function rateText(habit) {
    if (habit.inProgress) {
      return (
        pct(habit.rate) +
        ' <small>· ' + habit.inProgress.done + "/" + habit.inProgress.target +
        " " + escapeHtml(i18n("inProgress")) + "</small>"
      );
    }
    // Nothing was owed in this window — an archived habit's later months, or a
    // weekly one whose only week has not finished. "0%" would read as a miss.
    if (!habit.due) return "–";
    return pct(habit.rate);
  }

  /* ---------- views ---------- */

  function weekView() {
    var head = state.dow
      .map(function (label) {
        return "<th>" + escapeHtml(label) + "</th>";
      })
      .join("");
    var perDay = [];
    for (var d = 0; d < 7; d++) perDay.push({ done: 0, due: 0 });

    var rows = state.habits
      .map(function (habit) {
        var cells = "";
        for (var index = 0; index < 7; index++) {
          var char = habit.levels.charAt(index);
          if (char === "0" || char === "1" || char === "2") {
            perDay[index].due += 1;
            if (char === "2") perDay[index].done += 1;
          }
          cells += "<td>" + cell(habit, index) + "</td>";
        }
        return (
          '<tr class="' + (habit.archived ? "archived" : "") + '"' + tint(habit) + ">" +
          '<td class="name">' + habitName(habit) + "</td>" +
          cells +
          '<td class="rate">' + rateText(habit) + "</td></tr>"
        );
      })
      .join("");

    var totals = perDay
      .map(function (entry) {
        return "<td>" + (entry.due ? entry.done + "/" + entry.due : "–") + "</td>";
      })
      .join("");

    return (
      '<table class="awd-rep-table"><thead><tr>' +
      '<th class="name"></th>' + head + "<th></th></tr></thead>" +
      "<tbody>" + rows + "</tbody>" +
      "<tfoot><tr><td class=\"name\">" + escapeHtml(i18n("total")) + "</td>" +
      totals + '<td class="rate">' + pct(state.summary.rate) + "</td></tr></tfoot>" +
      "</table>"
    );
  }

  function monthView() {
    var blanks = leadingBlanks(state.first);
    var cards = state.habits
      .map(function (habit) {
        var head = state.dow
          .map(function (label) {
            return '<span class="dow">' + escapeHtml(label) + "</span>";
          })
          .join("");
        var body = "";
        for (var pad = 0; pad < blanks; pad++) {
          body += '<span class="awd-cell blank"></span>';
        }
        for (var index = 0; index < habit.levels.length; index++) {
          body += cell(habit, index);
        }
        return (
          '<div class="awd-rep-month"' + tint(habit) + ">" +
          "<h4>" + habitName(habit) +
          '<span class="pct">' + rateText(habit) + "</span></h4>" +
          '<div class="awd-rep-cal">' + head + body + "</div></div>"
        );
      })
      .join("");
    return '<div class="awd-rep-months">' + cards + "</div>";
  }

  /* The year view is the shared heatmap component — the same builder the
     dashboard's activity grid uses, so the two look like one idea and the month
     labels float instead of prising the columns apart. It builds DOM rather
     than a string, so this view is appended after the rest of the page. */

  function yearStrips(host) {
    if (!window.AwdHeatmap) return;
    state.habits.forEach(function (habit, index) {
      var strip = host.querySelector('.awd-rep-strip[data-index="' + index + '"]');
      if (!strip) return;
      strip.appendChild(
        AwdHeatmap.grid({
          first: state.first,
          last: state.last,
          firstDay: state.firstDay,
          months: state.months,
          classFor: function (day) {
            var char = habit.levels.charAt(dayIndex(day)) || "-";
            var classes = CELL_CLASS[char] || "off";
            if (day === state.today && char !== "x") classes += " today";
            return classes;
          },
          titleFor: function (day) {
            return cellTitle(habit, day);
          },
        })
      );
      AwdHeatmap.scrollTo(strip, state.today);
    });
  }

  function dayIndex(day) {
    return Math.round(
      (toDate(day).getTime() - toDate(state.first).getTime()) / 86400000
    );
  }

  function yearView() {
    return state.habits
      .map(function (habit, index) {
        var meta =
          "🔥 " + habit.streak + " " +
          escapeHtml(habit.weekly ? i18n("weeks") : i18n("days")) +
          " · " + escapeHtml(i18n("best")) + " " + habit.longest +
          " · " + rateText(habit);
        return (
          '<div class="awd-rep-year"' + tint(habit) + ">" +
          "<h4>" + habitName(habit) + '<span class="meta">' + meta + "</span></h4>" +
          '<div class="awd-rep-strip awd-hm" data-index="' + index + '"></div>' +
          "</div>"
        );
      })
      .join("");
  }

  /* ---------- chrome ---------- */

  function tiles() {
    var summary = state.summary;
    var entries = [
      [pct(summary.rate), i18n("completion")],
      [summary.perfect + "<small> " + escapeHtml(i18n("days")) + "</small>",
       i18n("perfect")],
      [String(summary.ticks), i18n("ticks")],
      // Python picks the pool so the unit is never mixed — see payload().
      [summary.longest + "<small> " +
       escapeHtml(i18n(summary.streakUnit === "weeks" ? "weeks" : "days")) +
       "</small>", i18n("longest")],
    ];
    return (
      '<div class="awd-rep-tiles">' +
      entries
        .map(function (entry) {
          return (
            '<div class="awd-rep-tile"><div class="v">' + entry[0] +
            '</div><div class="k">' + escapeHtml(entry[1]) + "</div></div>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  function top() {
    var tabs = ["week", "month", "year"]
      .map(function (view) {
        return (
          '<button class="awd-rep-tab' + (state.view === view ? " active" : "") +
          '" onclick="AwdRep.view(\'' + view + '\')">' +
          escapeHtml(i18n(view)) + "</button>"
        );
      })
      .join("");
    return (
      '<div class="awd-rep-top">' +
      '<h2 class="awd-rep-title">' + escapeHtml(state.title) + "</h2>" +
      '<div class="awd-rep-nav">' +
      '<button class="awd-rep-arrow" title="' + escapeHtml(i18n("prev")) +
      '" onclick="AwdRep.go(-1)">‹</button>' +
      '<button class="awd-rep-arrow" title="' + escapeHtml(i18n("today")) +
      '" onclick="AwdRep.today()">•</button>' +
      '<button class="awd-rep-arrow" title="' + escapeHtml(i18n("next")) + '"' +
      (state.canNext ? "" : " disabled") +
      ' onclick="AwdRep.go(1)">›</button></div>' +
      '<div class="awd-rep-seg">' + tabs + "</div></div>"
    );
  }

  function foot() {
    return (
      '<div class="awd-rep-foot"><label class="awd-switch">' +
      '<input type="checkbox"' + (state.hideArchived ? "" : " checked") +
      ' onchange="AwdRep.archived(this.checked)">' +
      '<span class="awd-switch-track"><span class="awd-switch-knob"></span></span>' +
      '<span>' + escapeHtml(i18n("showArchived")) + "</span></label></div>"
    );
  }

  /* ---------- entry points ---------- */

  AwdRep.render = function (data) {
    clearTimeout(busyTimer);
    state = data;
    var where = host();
    if (!where) return;
    var body;
    if (!state.habits.length) {
      body =
        '<div class="awd-rep-empty"><div class="awd-empty-title">' +
        escapeHtml(i18n("empty")) + '</div><div class="awd-empty-hint">' +
        escapeHtml(i18n("emptyHint")) + "</div></div>";
    } else if (state.view === "month") {
      body = monthView();
    } else if (state.view === "year") {
      body = yearView();
    } else {
      body = weekView();
    }
    where.innerHTML =
      top() + (state.habits.length ? tiles() : "") + body + foot();
    if (state.view === "year") yearStrips(where);
  };

  /* Python could not build the payload. Say so — a report stuck on its spinner
     forever is the failure mode this replaces. */
  AwdRep.failed = function (message) {
    clearTimeout(busyTimer);
    // Make sure the layer is up: a failure on the way *in* has to be visible,
    // and there is nowhere else for it to be seen.
    var shell = overlay();
    if (shell && shell.hidden) {
      shell.hidden = false;
      document.documentElement.classList.add("awd-rep-open");
    }
    var where = host();
    if (!where) return;
    where.innerHTML =
      '<div class="awd-rep-empty"><div class="awd-empty-title">' +
      escapeHtml(i18n("failed") || "Could not build the report") +
      '</div><div class="awd-empty-hint">' + escapeHtml(message || "") +
      "</div></div>";
  };

  AwdRep.view = function (view) {
    send("view:" + view);
  };
  AwdRep.go = function (steps) {
    send("nav:" + steps);
  };
  AwdRep.today = function () {
    send("today");
  };
  /* Named, not 0/1. The digits meant "hideArchived", the switch means "show",
     and the two ends read them in opposite directions — so ticking the box set
     hideArchived to true and nothing appeared to happen. */
  AwdRep.archived = function (shown) {
    send("archived:" + (shown ? "show" : "hide"));
  };

  /* ---------- the overlay ---------- */

  /* Python calls busy() first and then open() with the payload, so the screen is
     never blank and never empty — the spinner is up before the numbers exist. */
  AwdRep.busy = function () {
    var shell = overlay();
    if (!shell) return;
    shell.hidden = false;
    document.documentElement.classList.add("awd-rep-open");
    showBusy();
  };

  AwdRep.open = function (data) {
    AwdRep.busy();
    AwdRep.render(data);
  };

  AwdRep.close = function () {
    clearTimeout(busyTimer);
    var shell = overlay();
    if (!shell) return;
    shell.hidden = true;
    document.documentElement.classList.remove("awd-rep-open");
  };

  document.addEventListener("keydown", function (event) {
    var shell = overlay();
    if (event.key === "Escape" && shell && !shell.hidden) {
      event.preventDefault();
      AwdRep.close();
    }
  });
})();
