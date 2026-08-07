/* ============================================================
   reviewer_chrome.js — fills the in-page reviewer header/footer.
   Python pushes state through AwdRev.question / AwdRev.answer
   on the reviewer_did_show_question / _answer hooks.
   ============================================================ */

(function () {
  "use strict";

  var AwdRev = (window.AwdRev = window.AwdRev || {});
  var COUNT_CLASSES = ["new", "learn", "due"];

  function el(id) {
    return document.getElementById(id);
  }

  function renderShared(data) {
    var title = el("awd-rev-title");
    if (title) title.textContent = data.deck || "";

    var counts = el("awd-rev-counts");
    if (!counts) return;
    if (!data.showCounts || !data.counts) {
      counts.innerHTML = "";
      return;
    }
    counts.innerHTML = data.counts
      .map(function (value, index) {
        var current = index === data.current ? " current" : "";
        return (
          '<span class="awd-rev-count ' +
          COUNT_CLASSES[index] +
          current +
          '">' +
          value +
          "</span>"
        );
      })
      .join('<span class="awd-rev-plus">+</span>');
  }

  AwdRev.question = function (data) {
    renderShared(data);
    var actions = el("awd-rev-actions");
    if (!actions) return;
    actions.innerHTML =
      '<button class="awd-rev-show" onclick="pycmd(\'ans\')">' +
      escapeHtml(data.showAnswer || "Show Answer") +
      "</button>";
  };

  AwdRev.answer = function (data) {
    renderShared(data);
    var actions = el("awd-rev-actions");
    if (!actions) return;
    var buttons = data.buttons || [];
    if (!buttons.length) {
      actions.innerHTML = "";
      return;
    }
    actions.innerHTML =
      '<div class="awd-rev-rates">' +
      buttons
        .map(function (button) {
          // The interval string comes straight from the scheduler, so it
          // already respects deck presets and FSRS.
          var interval = button.interval
            ? '<span class="awd-rev-rate-t">' +
              escapeHtml(stripTags(button.interval)) +
              "</span>"
            : "";
          return (
            '<button class="awd-rev-rate ease' +
            button.ease +
            '" onclick="pycmd(\'ease' +
            button.ease +
            "')\">" +
            interval +
            '<span class="awd-rev-rate-l">' +
            escapeHtml(button.label) +
            "</span></button>"
          );
        })
        .join("") +
      "</div>";
  };

  function stripTags(text) {
    var holder = document.createElement("div");
    holder.innerHTML = text;
    return holder.textContent || "";
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[ch];
    });
  }
})();
