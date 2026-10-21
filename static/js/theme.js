// Sahifa chizilishidan oldin saqlangan rang rejimini qo'llaydi (miltillashning oldini oladi).
(function () {
  try {
    var t = localStorage.getItem("sp-theme");
    if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* localStorage yopiq bo'lishi mumkin */ }
})();
