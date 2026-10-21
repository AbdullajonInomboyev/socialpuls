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
    form.addEventListener("submit", function (e) {
      var btn = e.submitter || form.querySelector("button[type=submit]");
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


  // ---------- Yutuq formasi: mezon tanlanganda darajalar ----------
  var levelsEl = document.getElementById("levels-data");
  var grid = document.querySelector("[data-crit-grid]");
  if (levelsEl && grid) {
    var levels = JSON.parse(levelsEl.textContent || "{}");
    var wrap = document.querySelector("[data-level-wrap]");
    var select = document.querySelector("[data-level-select]");
    var fullNote = document.querySelector("[data-full-note]");
    var syncLevels = function () {
      var picked = grid.querySelector("input:checked");
      var list = picked ? (levels[picked.value] || []) : [];
      var keep = select.getAttribute("data-selected") || select.value;
      while (select.options.length > 1) select.remove(1);
      list.forEach(function (lv) {
        var o = document.createElement("option");
        o.value = lv[0];
        o.textContent = lv[1] + " (" + lv[2].replace(/\.?0+$/, "").replace(".", ",") + " ball)";
        if (lv[0] === keep) o.selected = true;
        select.appendChild(o);
      });
      select.setAttribute("data-selected", "");
      wrap.hidden = list.length === 0;
      if (fullNote) fullNote.hidden = !(picked && picked.closest(".crit-card").classList.contains("is-full"));
    };
    grid.addEventListener("change", syncLevels);
    syncLevels();
  }

  // ---------- Fayl tanlash: ro'yxat, hajm va tur bo'yicha oldindan ogohlantirish ----------
  var fileInput = document.querySelector("[data-file-input]");
  if (fileInput) {
    var zone = fileInput.closest("[data-dropzone]");
    var preview = document.querySelector("[data-file-preview]");
    var maxMb = parseInt(fileInput.getAttribute("data-max-mb"), 10) || 10;
    var okExt = /\.(pdf|jpe?g|png|webp)$/i;
    var human = function (n) { return n >= 1048576 ? (n / 1048576).toFixed(1).replace(".", ",") + " MB" : Math.max(1, Math.round(n / 1024)) + " KB"; };
    var render = function () {
      preview.textContent = "";
      Array.prototype.forEach.call(fileInput.files, function (f) {
        var li = document.createElement("li");
        var name = document.createElement("span");
        name.className = "fname";
        name.textContent = f.name;
        var info = document.createElement("span");
        info.className = "subtle";
        var problem = !okExt.test(f.name) ? "turi mos emas" : (f.size > maxMb * 1048576 ? maxMb + " MB dan katta" : "");
        info.textContent = problem ? human(f.size) + ", " + problem : human(f.size);
        if (problem) li.className = "bad";
        li.appendChild(name);
        li.appendChild(info);
        preview.appendChild(li);
      });
    };
    fileInput.addEventListener("change", render);
    ["dragenter", "dragover"].forEach(function (ev) { zone.addEventListener(ev, function () { zone.classList.add("is-over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { zone.addEventListener(ev, function () { zone.classList.remove("is-over"); }); });
  }

  // ---------- Tekshiruv: daraja tugmasi ballni to'ldiradi ----------
  document.querySelectorAll("[data-fill-points]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.closest("form").querySelector("input[name=points]");
      input.value = btn.getAttribute("data-fill-points").replace(/\.?0+$/, "");
      document.querySelectorAll("[data-fill-points]").forEach(function (b) { b.classList.toggle("is-picked", b === btn); });
      input.focus();
    });
  });

  // ---------- Qo'lda baholash: noto'g'ri qiymatni darhol belgilash ----------
  document.querySelectorAll(".score-input").forEach(function (input) {
    var max = parseFloat(input.getAttribute("data-max"));
    var check = function () {
      var v = input.value.trim().replace(",", ".");
      var bad = v !== "" && (isNaN(Number(v)) || Number(v) < 0 || Number(v) > max);
      input.classList.toggle("is-bad", bad);
      input.setAttribute("aria-invalid", bad ? "true" : "false");
    };
    input.addEventListener("input", check);
  });


  // ---------- Mezonlar muharriri: faol mezonlar yig'indisini jonli ko'rsatish ----------
  var critTable = document.querySelector("[data-crit-table]");
  if (critTable) {
    var totalEl = document.querySelector("[data-crit-total]");
    var recount = function () {
      var sum = 0;
      critTable.querySelectorAll("tbody tr").forEach(function (tr) {
        var on = tr.querySelector("[data-crit-active]");
        var max = tr.querySelector("[data-crit-max]");
        if (on && on.checked && max) sum += parseInt(max.value, 10) || 0;
      });
      totalEl.textContent = sum;
      totalEl.classList.toggle("is-off", sum !== 100);
    };
    critTable.addEventListener("input", recount);
    critTable.addEventListener("change", recount);
    recount();
  }

  // Toast xabarlari
  document.querySelectorAll("[data-toast]").forEach(function (t) {
    var close = function () { t.remove(); };
    var b = t.querySelector("[data-dismiss]");
    if (b) b.addEventListener("click", close);
    if (!t.classList.contains("error")) setTimeout(close, 6000);
  });
})();
