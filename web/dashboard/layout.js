/* ============================================================
   layout.js — the dashboard's widgets: edit mode, remove and
   add back, size, drag to reorder.

   Everything happens in the page and the whole layout is sent
   back as `awd:layout:<json>` after each change; Python only
   stores it. Nothing here ever asks for a re-render, which is
   what keeps a drag at one frame per slot change rather than
   one per mouse event.
   ============================================================ */

(function () {
  "use strict";

  var Awd = (window.Awd = window.Awd || {});
  var SIZES = ["xs", "s", "m", "l"];
  var HOLD_MS = 120;
  var MOVE_PX = 4;
  var EDGE_PX = 48;

  function data() {
    return window.AWD_DATA || {};
  }

  function i18n(key) {
    return (data().i18n || {})[key] || key;
  }

  function meta(id) {
    return (data().widgets || {})[id] || { name: id, icon: "", sizes: ["l"] };
  }

  function root() {
    return document.getElementById("awd-root");
  }

  function widgets() {
    var host = root();
    return host ? Array.prototype.slice.call(host.querySelectorAll(".awd-widget")) : [];
  }

  function editing() {
    return document.documentElement.classList.contains("awd-edit");
  }

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function persist() {
    if (typeof pycmd !== "function") return;
    var entries = widgets().map(function (w) {
      return { id: w.dataset.widget, size: w.dataset.size, hidden: w.hidden };
    });
    pycmd("awd:layout:" + JSON.stringify(entries));
  }

  /* ---------- chrome: badge, size pill, bar, gallery ---------- */

  var built = false;
  var gallery = null;

  function sizePill(w) {
    var allowed = meta(w.dataset.widget).sizes;
    if (allowed.length < 2) return "";
    var pills = SIZES.map(function (size) {
      var cls = size === w.dataset.size ? "on" : allowed.indexOf(size) < 0 ? "off" : "";
      return '<b data-size="' + size + '" class="' + cls + '">' + size.toUpperCase() + "</b>";
    });
    return '<span class="awd-w-size">' + pills.join("") + "</span>";
  }

  function decorate(w) {
    if (w.querySelector(".awd-w-remove")) return;
    w.insertAdjacentHTML(
      "beforeend",
      '<button class="awd-w-remove" title="' + escapeHtml(i18n("widgetRemove")) + '">−</button>' +
        sizePill(w)
    );
  }

  function setSize(w, size) {
    w.dataset.size = size;
    w.querySelectorAll(".awd-w-size b").forEach(function (b) {
      b.classList.toggle("on", b.dataset.size === size);
    });
  }

  function afterShow(id) {
    if (id === "heatmap" && Awd.buildHeatmap) Awd.buildHeatmap();
  }

  function renderGallery() {
    var grid = gallery.querySelector(".awd-gallery-grid");
    var hidden = widgets().filter(function (w) {
      return w.hidden;
    });
    if (!hidden.length) {
      grid.innerHTML = '<div class="awd-gallery-empty">' + escapeHtml(i18n("galleryEmpty")) + "</div>";
      return;
    }
    grid.innerHTML = hidden
      .map(function (w) {
        var id = w.dataset.widget;
        var m = meta(id);
        // The deck list lives in the sidebar while that is on; adding the
        // widget would show nothing, so the gallery says where it went.
        var elsewhere = id === "decks" && data().decksInSidebar;
        return (
          '<button class="awd-gallery-item" data-widget="' + id + '"' + (elsewhere ? " disabled" : "") + ">" +
          '<span class="awd-gallery-ic">' + m.icon + "</span><b>" + escapeHtml(m.name) + "</b>" +
          (elsewhere ? "<span>" + escapeHtml(i18n("inSidebar")) + "</span>" : "") +
          "</button>"
        );
      })
      .join("");
  }

  function build() {
    built = true;
    widgets().forEach(decorate);

    root().addEventListener("click", function (event) {
      if (!editing()) return;
      var remove = event.target.closest(".awd-w-remove");
      if (remove) {
        remove.closest(".awd-widget").hidden = true;
        persist();
        if (gallery.classList.contains("open")) renderGallery();
        return;
      }
      var size = event.target.closest(".awd-w-size b");
      if (size && !size.classList.contains("off")) {
        setSize(size.closest(".awd-widget"), size.dataset.size);
        persist();
      }
    });

    var bar = document.createElement("div");
    bar.className = "awd-editbar";
    bar.innerHTML =
      '<button class="awd-pill awd-pill-ghost" id="awd-widget-add">+&nbsp;' +
      escapeHtml(i18n("widgetAdd")) + "</button>" +
      '<button class="awd-pill awd-pill-accent" id="awd-widget-done">' +
      escapeHtml(i18n("widgetsDone")) + "</button>";
    document.body.appendChild(bar);

    gallery = document.createElement("div");
    gallery.className = "awd-gallery";
    gallery.innerHTML = "<h3>" + escapeHtml(i18n("galleryTitle")) + '</h3><div class="awd-gallery-grid"></div>';
    document.body.appendChild(gallery);

    document.getElementById("awd-widget-add").addEventListener("click", function () {
      renderGallery();
      gallery.classList.toggle("open");
    });
    document.getElementById("awd-widget-done").addEventListener("click", function () {
      Awd.editWidgets(false);
    });
    gallery.addEventListener("click", function (event) {
      var item = event.target.closest(".awd-gallery-item");
      if (!item || item.disabled) return;
      var w = root().querySelector('.awd-widget[data-widget="' + item.dataset.widget + '"]');
      if (!w) return;
      w.hidden = false;
      afterShow(item.dataset.widget);
      persist();
      renderGallery();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && editing()) Awd.editWidgets(false);
    });
  }

  Awd.editWidgets = function (on) {
    if (on === undefined) on = !editing();
    if (on && !built) build();
    if (!on && drag) finish(false);
    document.documentElement.classList.toggle("awd-edit", on);
    if (!on && gallery) gallery.classList.remove("open");
  };

  /* ---------- drag to reorder ----------
     The deck list's gesture: pointer events, a short hold, a ghost that
     follows on `transform`. The source stays in the grid as the placeholder
     and only moves when the pointer asks for another slot; the others slide
     over with a FLIP — one transform transition per slot change, never work
     per mouse event. */

  var drag = null;

  function order() {
    return widgets()
      .map(function (w) {
        return w.dataset.widget;
      })
      .join(",");
  }

  function far() {
    return Math.abs(drag.lastX - drag.x) + Math.abs(drag.lastY - drag.y) >= MOVE_PX;
  }

  document.addEventListener("pointerdown", function (event) {
    if (!editing() || drag || event.button !== 0) return;
    if (event.target.closest(".awd-w-remove, .awd-w-size, .awd-editbar, .awd-gallery")) return;
    var w = event.target.closest(".awd-widget");
    if (!w || w.hidden || !root().contains(w)) return;
    var rect = w.getBoundingClientRect();
    drag = {
      pointerId: event.pointerId,
      w: w,
      x: event.clientX,
      y: event.clientY,
      lastX: event.clientX,
      lastY: event.clientY,
      offsetX: event.clientX - rect.left,
      offsetY: event.clientY - rect.top,
      width: rect.width,
      height: rect.height,
      armed: false,
      active: false,
      ghost: null,
      raf: 0,
      order: order(),
      timer: setTimeout(function () {
        if (!drag) return;
        drag.armed = true;
        if (far()) start();
      }, HOLD_MS),
    };
  });

  document.addEventListener("pointermove", function (event) {
    if (!drag || event.pointerId !== drag.pointerId) return;
    drag.lastX = event.clientX;
    drag.lastY = event.clientY;
    if (!drag.active) {
      if (!drag.armed || !far()) return;
      start();
    }
    track();
  });

  document.addEventListener("pointerup", function (event) {
    if (drag && event.pointerId === drag.pointerId) finish(true);
  });
  document.addEventListener("pointercancel", function (event) {
    if (drag && event.pointerId === drag.pointerId) finish(false);
  });
  window.addEventListener("blur", function () {
    if (drag) finish(false);
  });

  function start() {
    drag.active = true;
    var ghost = document.createElement("div");
    ghost.className = "awd-drag-ghost awd-widget-ghost";
    ghost.style.width = drag.width + "px";
    ghost.style.height = drag.height + "px";
    ghost.appendChild(drag.w.firstElementChild.cloneNode(true));
    document.body.appendChild(ghost);
    drag.ghost = ghost;
    drag.w.classList.add("awd-drag-source");
    document.documentElement.classList.add("awd-dnd");
    var tick = function () {
      autoScroll();
      drag.raf = requestAnimationFrame(tick);
    };
    drag.raf = requestAnimationFrame(tick);
    track();
  }

  function track() {
    drag.ghost.style.transform =
      "translate(" + (drag.lastX - drag.offsetX) + "px," + (drag.lastY - drag.offsetY) + "px)";
    var el = document.elementFromPoint(drag.lastX, drag.lastY);
    var target = el && el.closest ? el.closest(".awd-widget") : null;
    if (!target || target === drag.w || target.hidden || !root().contains(target)) return;
    var rect = target.getBoundingClientRect();
    // A full-row widget is passed above or below; anything narrower, left
    // or right of its middle.
    var before =
      target.dataset.size === "l"
        ? drag.lastY < rect.top + rect.height / 2
        : drag.lastX < rect.left + rect.width / 2;
    var anchor = before ? target : target.nextElementSibling;
    if (anchor === drag.w || drag.w.nextElementSibling === anchor) return;
    reorder(anchor);
  }

  function reorder(anchor) {
    var items = widgets().filter(function (w) {
      return !w.hidden;
    });
    var first = items.map(function (w) {
      return w.getBoundingClientRect();
    });
    root().insertBefore(drag.w, anchor);
    // Measure the new layout with no transform in the way, then play each
    // widget from where it was to where it is.
    items.forEach(function (w) {
      w.classList.remove("awd-flip");
      w.style.transform = "";
    });
    items.forEach(function (w, i) {
      var last = w.getBoundingClientRect();
      var dx = first[i].left - last.left;
      var dy = first[i].top - last.top;
      if (!dx && !dy) return;
      w.style.transform = "translate(" + dx + "px," + dy + "px)";
      requestAnimationFrame(function () {
        w.classList.add("awd-flip");
        w.style.transform = "";
      });
    });
  }

  function autoScroll() {
    var step = 0;
    if (drag.lastY < EDGE_PX) {
      step = -Math.ceil((EDGE_PX - drag.lastY) / 4);
    } else if (drag.lastY > window.innerHeight - EDGE_PX) {
      step = Math.ceil((drag.lastY - (window.innerHeight - EDGE_PX)) / 4);
    }
    if (!step) return;
    window.scrollBy(0, Math.max(-24, Math.min(24, step)));
    track();
  }

  function finish(drop) {
    var state = drag;
    drag = null;
    clearTimeout(state.timer);
    if (!state.active) return;
    cancelAnimationFrame(state.raf);
    state.ghost.remove();
    state.w.classList.remove("awd-drag-source");
    document.documentElement.classList.remove("awd-dnd");
    // Saved whether the pointer was released or lost: the page shows this
    // order now, so the stored one has to match it.
    if (order() !== state.order) persist();
    void drop;
  }
})();
