/* ============================================================
   Awesome Dashboard card skin — flip interactions.
   - Click the question card (or press Space) → show answer.
   - On the answer: click the card or press Space → flip between
     front/back with a horizontal rotateY animation.
   ============================================================ */

(function () {
  "use strict";

  var AwdSkin = (window.AwdSkin = window.AwdSkin || {});

  function onInteractive(target) {
    return (
      target.closest &&
      target.closest(
        "a, button, details, summary, input, textarea, select, audio, video, [contenteditable]"
      )
    );
  }

  /* question side: click anywhere on the card to reveal the answer */
  AwdSkin.reveal = function (event) {
    if (onInteractive(event.target)) return;
    if (typeof pycmd === "function") pycmd("ans");
  };

  /* answer side: toggle the horizontal flip */
  AwdSkin.toggleFlip = function () {
    var inner = document.getElementById("awd-flip");
    if (inner) inner.classList.toggle("flipped");
  };

  AwdSkin.click = function (event) {
    if (AwdSkin._suppressClick) return;
    if (onInteractive(event.target)) return;
    AwdSkin.toggleFlip();
  };

  /* --- rate with a fly-away animation, then answer --- */

  var FLY = {
    left: "translateX(-130vw) rotate(-12deg)",
    right: "translateX(130vw) rotate(12deg)",
    up: "translateY(-120vh) rotate(4deg)",
    down: "translateY(120vh) rotate(-4deg)",
  };

  AwdSkin.flyAnswer = function (direction, ease) {
    if (AwdSkin._flying) return;
    var scene =
      document.querySelector(".awd-flip-scene") ||
      document.querySelector("#qa .awd-skin");
    if (!scene) {
      if (typeof pycmd === "function") pycmd("ease" + ease);
      return;
    }
    AwdSkin._flying = true;
    scene.style.transition =
      "transform .32s cubic-bezier(.5, 0, .9, .4), opacity .32s ease";
    scene.style.transform = FLY[direction] || FLY.right;
    scene.style.opacity = "0";
    setTimeout(function () {
      if (typeof pycmd === "function") pycmd("ease" + ease);
      AwdSkin._flying = false;
    }, 300);
  };

  /* --- mouse/touch swipe on the answer card --- */

  var drag = { active: false, moved: false, scene: null, x: 0, y: 0 };

  document.addEventListener("pointerdown", function (event) {
    if (AwdSkin._flying) return;
    var scene = event.target.closest && event.target.closest(".awd-flip-scene");
    if (!scene || onInteractive(event.target)) return;
    drag.active = true;
    drag.moved = false;
    drag.scene = scene;
    drag.x = event.clientX;
    drag.y = event.clientY;
  });

  document.addEventListener("pointermove", function (event) {
    if (!drag.active || !drag.scene) return;
    var dx = event.clientX - drag.x;
    var dy = event.clientY - drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 6) drag.moved = true;
    drag.scene.style.transition = "none";
    drag.scene.style.transform =
      "translate(" + dx + "px," + dy + "px) rotate(" + dx * 0.04 + "deg)";
  });

  document.addEventListener("pointerup", function (event) {
    if (!drag.active || !drag.scene) return;
    var scene = drag.scene;
    var dx = event.clientX - drag.x;
    var dy = event.clientY - drag.y;
    drag.active = false;
    drag.scene = null;

    var THRESHOLD = 90;
    var direction = null;
    var ease = 0;
    if (Math.abs(dx) >= Math.abs(dy)) {
      if (dx <= -THRESHOLD) { direction = "left"; ease = 1; }
      else if (dx >= THRESHOLD) { direction = "right"; ease = 4; }
    } else {
      if (dy <= -THRESHOLD) { direction = "up"; ease = 2; }
      else if (dy >= THRESHOLD) { direction = "down"; ease = 3; }
    }

    if (drag.moved) {
      AwdSkin._suppressClick = true;
      setTimeout(function () { AwdSkin._suppressClick = false; }, 60);
    }

    if (direction) {
      AwdSkin.flyAnswer(direction, ease);
    } else {
      scene.style.transition = "transform .25s ease";
      scene.style.transform = "";
    }
  });

  /* When the answer scene is inserted it starts on the front face; flip it
     to the back on the next frame so the horizontal turn is animated. */
  var observer = new MutationObserver(function () {
    var inner = document.getElementById("awd-flip");
    if (inner && !inner.dataset.awdFlipped) {
      inner.dataset.awdFlipped = "1";
      AwdSkin._flying = false; // fresh card — reset gesture state
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          inner.classList.add("flipped");
        });
      });
    }
  });

  function boot() {
    var qa = document.getElementById("qa");
    if (qa) {
      observer.observe(qa, { childList: true, subtree: true });
    } else {
      setTimeout(boot, 120);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
