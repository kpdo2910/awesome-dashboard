/* ============================================================
   theme.js — applies a palette to the live page.

   Python calls AwdTheme.apply(vars) instead of re-rendering, so
   switching theme or light/dark cross-fades in place.
   ============================================================ */

(function () {
  "use strict";

  var AwdTheme = (window.AwdTheme = window.AwdTheme || {});
  var timer = null;

  AwdTheme.apply = function (vars) {
    var root = document.documentElement;
    root.classList.add("awd-theming");
    for (var name in vars) {
      if (Object.prototype.hasOwnProperty.call(vars, name)) {
        root.style.setProperty(name, vars[name]);
      }
    }
    // Drop the transition once the fade is done so it can't interfere with
    // anything else on the page.
    clearTimeout(timer);
    timer = setTimeout(function () {
      root.classList.remove("awd-theming");
    }, 420);
  };

  AwdTheme.setNightMode = function (night) {
    document.documentElement.classList.toggle("night-mode", !!night);
    document.body && document.body.classList.toggle("night-mode", !!night);
  };
})();
