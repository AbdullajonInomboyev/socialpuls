// Social Puls: umumiy interfeys xatti-harakatlari (menyu, rang rejimi, parol, tasma izohi, toast).
(function () {
  "use strict";
  var root = document.documentElement;

  function isDark() {
    var t = root.getAttribute("data-theme");
    if (t) return t === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("sp-theme", next); } catch (e) {}
    });
  });

  // Foydalanuvchi menyusi
  document.querySelectorAll("[data-menu]").forEach(function (menu) {
    var btn = menu.querySelector("[data-menu-button]");
    var panel = menu.querySelector("[data-menu-panel]");
    function set(open) {
      panel.setAttribute("data-open", open ? "true" : "false");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    }
    btn.addEventListener("click", function (e) { e.stopPropagation(); set(panel.getAttribute("data-open") !== "true"); });
    document.addEventListener("click", function (e) { if (!menu.contains(e.target)) set(false); });
    menu.addEventListener("keydown", function (e) { if (e.key === "Escape") { set(false); btn.focus(); } });
  });

  // Mobil yon panel
  var rail = document.querySelector("[data-rail]");
  var backdrop = document.querySelector("[data-rail-backdrop]");
  var railBtn = document.querySelector("[data-rail-toggle]");
  function setRail(open) {
    if (!rail) return;
    rail.setAttribute("data-open", open ? "true" : "false");
    if (backdrop) backdrop.setAttribute("data-open", open ? "true" : "false");
    if (railBtn) railBtn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { var first = rail.querySelector("a"); if (first) first.focus(); }
  }
  if (railBtn) railBtn.addEventListener("click", function () { setRail(rail.getAttribute("data-open") !== "true"); });
  if (backdrop) backdrop.addEventListener("click", function () { setRail(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && rail && rail.getAttribute("data-open") === "true") { setRail(false); if (railBtn) railBtn.focus(); }
  });

  // Parolni ko'rsatish
  document.querySelectorAll("[data-toggle-pass]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.parentElement.querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Parolni yashirish" : "Parolni ko'rsatish");
    });
  });

  // Forma yuborilganda tugmani band qilish (ikki marta bosilmasin)
  document.querySelectorAll("form[data-busy-form]").forEach(function (form) {
    form.addEventListener("submit", function () {
      var btn = form.querySelector("button[type=submit]");
      if (btn) { btn.setAttribute("aria-busy", "true"); setTimeout(function () { btn.disabled = true; }, 0); }
    });
  });

  // Tanlov o'zgarganda formani yuborish (davr tanlash)
  document.querySelectorAll("form[data-autosubmit] select").forEach(function (sel) {
    sel.addEventListener("change", function () { sel.form.submit(); });
  });

  // To'liq ekran
  document.querySelectorAll("[data-fullscreen]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!document.fullscreenElement) { if (root.requestFullscreen) root.requestFullscreen(); }
      else if (document.exitFullscreen) document.exitFullscreen();
    });
  });

  // Avto-chiqish taymeri: serverdagi IdleTimeoutMiddleware bilan bir xil vaqt.
  var idleBox = document.querySelector("[data-idle]");
  if (idleBox) {
    var limit = parseInt(idleBox.getAttribute("data-idle"), 10) * 60;
    var pingUrl = idleBox.getAttribute("data-ping");
    var timerEl = idleBox.querySelector("[data-idle-timer]");
    var lastActive = Date.now(), lastPing = Date.now();
    var pad = function (n) { return (n < 10 ? "0" : "") + n; };
    var tick = function () {
      var left = Math.max(0, limit - Math.floor((Date.now() - lastActive) / 1000));
      timerEl.textContent = pad(Math.floor(left / 60)) + ":" + pad(left % 60);
      if (left === 0) { window.location.reload(); }
    };
    var activity = function () {
      lastActive = Date.now();
      if (Date.now() - lastPing > 60000) {
        lastPing = Date.now();
        fetch(pingUrl, { credentials: "same-origin" }).catch(function () {});
      }
    };
    ["click", "keydown", "scroll", "mousemove", "touchstart"].forEach(function (ev) {
      window.addEventListener(ev, activity, { passive: true });
    });
    tick();
    setInterval(tick, 1000);
  }

  // Toast xabarlari
  document.querySelectorAll("[data-toast]").forEach(function (t) {
    var close = function () { t.remove(); };
    var b = t.querySelector("[data-dismiss]");
    if (b) b.addEventListener("click", close);
    if (!t.classList.contains("error")) setTimeout(close, 6000);
  });
})();
