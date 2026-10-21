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

  // Puls tasmasi izohi
  var tip = document.querySelector("[data-puls-tip]");
  if (!tip) { tip = document.createElement("div"); tip.className = "puls-tip"; tip.setAttribute("role", "tooltip"); document.body.appendChild(tip); }
  function showTip(seg) {
    tip.textContent = seg.getAttribute("data-tip");
    var r = seg.getBoundingClientRect();
    tip.setAttribute("data-show", "true");
    var w = tip.offsetWidth;
    var left = Math.min(Math.max(8, r.left + r.width / 2 - w / 2), window.innerWidth - w - 8);
    tip.style.left = left + "px";
    tip.style.top = Math.max(8, r.top - tip.offsetHeight - 8) + "px";
  }
  function hideTip() { tip.setAttribute("data-show", "false"); }
  document.querySelectorAll(".puls-seg[data-tip]").forEach(function (seg) {
    seg.addEventListener("mouseenter", function () { showTip(seg); });
    seg.addEventListener("focus", function () { showTip(seg); });
    seg.addEventListener("mouseleave", hideTip);
    seg.addEventListener("blur", hideTip);
  });
  window.addEventListener("scroll", hideTip, { passive: true });

  // Tanlov o'zgarganda formani yuborish (davr tanlash)
  document.querySelectorAll("form[data-autosubmit] select").forEach(function (sel) {
    sel.addEventListener("change", function () { sel.form.submit(); });
  });

  // Toast xabarlari
  document.querySelectorAll("[data-toast]").forEach(function (t) {
    var close = function () { t.remove(); };
    var b = t.querySelector("[data-dismiss]");
    if (b) b.addEventListener("click", close);
    if (!t.classList.contains("error")) setTimeout(close, 6000);
  });
})();
