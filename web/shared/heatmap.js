/* ============================================================
   heatmap.js — the GitHub-style calendar grid, shared by the
   dashboard's activity heatmap and the habit report's year view.

   The caller owns the data and the colours; this owns the shape:
   one column per week, seven cells down, and month labels that
   float inside their column instead of sitting in the flow.
   That last part is the whole point — a label in the flow widens
   the one column it lands in, which puts a gap at every month
   boundary and breaks the continuous grid.
   ============================================================ */

(function () {
  "use strict";

  var AwdHeatmap = (window.AwdHeatmap = window.AwdHeatmap || {});

  /* Days are YYYYMMDD integers, as everywhere else in the add-on. Midday, so a
     daylight-saving shift cannot roll a date over. */

  function toDate(day) {
    return new Date(
      Math.floor(day / 10000),
      (Math.floor(day / 100) % 100) - 1,
      day % 100,
      12
    );
  }

  function fromDate(date) {
    return (
      date.getFullYear() * 10000 + (date.getMonth() + 1) * 100 + date.getDate()
    );
  }

  AwdHeatmap.toDay = fromDate;
  AwdHeatmap.toDate = toDate;

  /* Weekday labels: a zero-width sticky column that overlays the first cells
     and only fades in on hover, so naming three of seven rows costs no width. */

  function labelColumn(labels) {
    var host = document.createElement("div");
    host.className = "awd-hm-labels";
    // The first slot lines up with the month-label lane above row one.
    var pad = document.createElement("span");
    pad.className = "awd-hm-pad";
    host.appendChild(pad);
    for (var row = 0; row < 7; row++) {
      var span = document.createElement("span");
      span.textContent = labels[row] || "";
      host.appendChild(span);
    }
    return host;
  }

  /**
   * Build the grid.
   *
   *   first, last     the period, inclusive, as YYYYMMDD integers
   *   firstDay        ISO weekday each column starts on (1 = Monday)
   *   months          twelve localised month names, January first
   *   classFor(day)   extra classes for that day's cell — the caller's colours
   *   titleFor(day)   optional tooltip text
   *   weekdayLabels   optional seven labels, in `firstDay` order
   *
   * Days outside [first, last] still get a cell, marked `pad`, so the first and
   * last weeks stay aligned to their weekday rows.
   */
  AwdHeatmap.grid = function (opts) {
    var first = opts.first;
    var last = opts.last;
    var firstDay = opts.firstDay || 1;
    var months = opts.months || [];
    var classFor = opts.classFor || function () { return ""; };
    var titleFor = opts.titleFor;

    var grid = document.createElement("div");
    grid.className = "awd-hm-grid";
    if (opts.weekdayLabels) grid.appendChild(labelColumn(opts.weekdayLabels));

    var cursor = toDate(first);
    // Back up to the column start on or before `first`.
    cursor.setDate(
      cursor.getDate() - (((cursor.getDay() || 7) - firstDay + 7) % 7)
    );
    var end = toDate(last);
    var lastMonth = -1;

    while (cursor <= end) {
      var col = document.createElement("div");
      col.className = "awd-hm-col";
      var labelled = false;

      for (var row = 0; row < 7; row++) {
        var day = fromDate(cursor);
        var cell = document.createElement("div");
        if (day < first || day > last) {
          cell.className = "awd-hm-cell pad";
        } else {
          if (!labelled && cursor.getMonth() !== lastMonth) {
            lastMonth = cursor.getMonth();
            var label = document.createElement("div");
            label.className = "awd-hm-month";
            label.textContent = months[lastMonth] || "";
            col.appendChild(label);
            labelled = true;
          }
          cell.className = "awd-hm-cell " + classFor(day);
          cell.dataset.day = String(day);
          if (titleFor) cell.title = titleFor(day);
        }
        col.appendChild(cell);
        cursor.setDate(cursor.getDate() + 1);
      }
      grid.appendChild(col);
    }
    return grid;
  };

  /** Scroll a grid's container so a given day is in view; today by default. */
  AwdHeatmap.scrollTo = function (host, day) {
    if (!host) return;
    var cell = day && host.querySelector('.awd-hm-cell[data-day="' + day + '"]');
    if (!cell) {
      host.scrollLeft = host.scrollWidth;
      return;
    }
    host.scrollLeft = Math.max(
      0,
      cell.offsetLeft - host.clientWidth / 2
    );
  };
})();
