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

  function two(value) {
    return (value < 10 ? "0" : "") + value;
  }

  /* ---------- pinned Pomodoro ----------
     Called two ways: inside every question/answer payload (so the widget is
     right as soon as the reviewer opens) and once per second from
     pomodoro.push() while a phase is running. */

  AwdRev.pomRender = function (state) {
    var host = el("awd-rev-pom");
    if (!host || !state) return;

    var idle = state.phase === "idle";
    // Idle shows the configured focus length, so the button reads as an offer
    // to start rather than an empty clock.
    var seconds = idle ? (state.focusMin || 25) * 60 : state.remaining;
    var timeEl = el("awd-rev-pom-time");
    if (timeEl) {
      timeEl.textContent =
        two(Math.floor(seconds / 60)) + ":" + two(seconds % 60);
    }

    host.className =
      "awd-rev-pom" +
      (idle ? " idle" : " " + state.phase) +
      (state.paused ? " paused" : "");

    var toggleEl = el("awd-rev-pom-toggle");
    if (toggleEl) {
      toggleEl.title = idle
        ? state.actionLabel || ""
        : (state.actionLabel || "") + " · " + (state.phaseLabel || "");
    }
    var skipEl = el("awd-rev-pom-skip");
    if (skipEl) {
      skipEl.hidden = idle;
      skipEl.title = state.skipLabel || "";
    }
  };


  /* ---------- auto-grading ---------- */

  function gradeBar(ag) {
    var bands = (ag.bands || [])
      .map(function (band) {
        return (
          '<span class="awd-ag-band ' + band.zone +
          '" style="width:' + band.width + '%"></span>'
        );
      })
      .join("");
    return (
      '<div class="awd-ag-track">' + bands +
      '<div class="awd-ag-spent" id="awd-ag-spent" style="animation-duration:' +
      ag.seconds + 's"></div>' +
      "</div>" +
      // Outside the track: it clips, and a caption in a 7px box is sliced.
      '<span class="awd-ag-paused">' + escapeHtml(ag.paused || "") + "</span>"
    );
  }

  function answerGrade(data) {
    var ag = data.autoGrade;
    var interval = ag.interval
      ? '<span class="awd-ag-int">' + escapeHtml(stripTags(ag.interval)) + "</span>"
      : "";
    return (
      '<div class="awd-ag answered zone-' + ag.zone + '" id="awd-ag">' +
      '<button class="awd-ag-pill" id="awd-ag-pill" title="' +
      escapeHtml(ag.pick || "") + '">' +
      '<span class="awd-ag-time">' + escapeHtml(String(ag.seconds)) + "s</span>" +
      '<span class="awd-ag-sep">&#8594;</span>' +
      '<span class="awd-ag-grade">' + escapeHtml(ag.label || "") + "</span>" +
      interval +
      "</button>" +
      (ag.keys || "") +
      "</div>"
    );
  }

  AwdRev.gradePause = function (paused) {
    var spent = el("awd-ag-spent");
    if (spent) spent.style.animationPlayState = paused ? "paused" : "running";
    var host = el("awd-ag");
    if (host) host.classList.toggle("paused", !!paused);
  };

  /* Bound once on the footer: the bar is rebuilt per card, so a listener
     added each render would stack up. */
  function bindReveal() {
    var actions = el("awd-rev-actions");
    if (!actions || actions.dataset.awdBound) return;
    actions.dataset.awdBound = "1";
    actions.addEventListener("click", function (event) {
      var pill = event.target.closest && event.target.closest(".awd-ag-pill");
      if (!pill) return;
      var host = el("awd-ag");
      var rates = actions.querySelector(".awd-rev-rates");
      if (host) host.hidden = true;
      if (rates) rates.hidden = false;
    });
  }

  function renderShared(data) {
    var title = el("awd-rev-title");
    if (title) title.textContent = data.deck || "";

    var undo = el("awd-rev-undo");
    if (undo && data.undo) {
      undo.disabled = !data.undo.can;
      undo.title = data.undo.label || "";
    }

    if (data.pom) AwdRev.pomRender(data.pom);

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
      (data.autoGrade ? '<div class="awd-ag" id="awd-ag">' +
                        gradeBar(data.autoGrade) + "</div>" : "") +
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
    var ag = data.autoGrade;
    actions.innerHTML =
      (ag ? answerGrade(data) : "") +
      '<div class="awd-rev-rates"' + (ag ? " hidden" : "") + ">" +
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
            (ag && ag.ease === button.ease ? " chosen" : "") +
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
    if (ag) bindReveal();
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
