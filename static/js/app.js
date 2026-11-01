(function () {
  "use strict";
  var doc = document;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var csrf = (doc.querySelector('meta[name="csrf-token"]') || {}).content || "";

  function $(sel, root) { return (root || doc).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || doc).querySelectorAll(sel)); }

  /* ---------- theme ---------- */
  var themeBtn = $("#theme-toggle");
  function currentTheme() { return doc.documentElement.getAttribute("data-theme") || "light"; }
  function setTheme(t, animate) {
    var root = doc.documentElement;
    if (animate && !reduceMotion) { root.classList.add("theme-anim"); setTimeout(function () { root.classList.remove("theme-anim"); }, 450); }
    root.setAttribute("data-theme", t);
    try { localStorage.setItem("am-theme", t); } catch (e) {}
    if (themeBtn) { themeBtn.textContent = t === "dark" ? "☀️" : "🌙"; themeBtn.setAttribute("aria-label", t === "dark" ? "Switch to light mode" : "Switch to dark mode"); }
  }
  if (themeBtn) { setTheme(currentTheme()); themeBtn.addEventListener("click", function () { setTheme(currentTheme() === "dark" ? "light" : "dark", true); }); }

  /* ---------- toasts ---------- */
  function toast(message, kind) {
    var box = $("#messages");
    if (!box) { box = doc.createElement("div"); box.id = "messages"; box.className = "messages"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite"); doc.body.appendChild(box); }
    var el = doc.createElement("div"); el.className = "msg " + (kind || "success"); el.textContent = message; box.appendChild(el);
    setTimeout(function () { el.style.transition = "opacity .4s"; el.style.opacity = "0"; setTimeout(function () { el.remove(); }, 450); }, 4200);
  }
  $$("#messages .msg").forEach(function (el) { setTimeout(function () { el.style.transition = "opacity .4s"; el.style.opacity = "0"; setTimeout(function () { el.remove(); }, 450); }, 5200); });

  /* ---------- helpers ---------- */
  function post(url, data) {
    var body = new URLSearchParams(data);
    return fetch(url, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest", "Content-Type": "application/x-www-form-urlencoded" }, body: body })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { j.status = r.status; return j; }); });
  }
  function setCount(el, n) { if (!el) return; el.textContent = n; el.hidden = !n; }

  /* ---------- mobile nav / search / dropdowns ---------- */
  var menuBtn = $("#menu-toggle"), nav = $("#navbar"), searchBox = $("#search-box"), searchBtn = $("#search-open");
  if (menuBtn && nav) menuBtn.addEventListener("click", function () { var o = nav.hidden; nav.hidden = !o; menuBtn.setAttribute("aria-expanded", String(o)); });
  if (searchBtn && searchBox) searchBtn.addEventListener("click", function () { searchBox.classList.toggle("open"); var i = $("input", searchBox); if (i) i.focus(); });
  $$(".dropdown > [data-dropdown]").forEach(function (btn) {
    btn.addEventListener("click", function (e) { e.stopPropagation(); var d = btn.parentElement, was = d.classList.contains("open"); $$(".dropdown.open").forEach(function (x) { x.classList.remove("open"); }); if (!was) { d.classList.add("open"); if (btn.id === "bell-btn") loadNotifications(); } btn.setAttribute("aria-expanded", String(!was)); });
  });
  doc.addEventListener("click", function (e) { if (!e.target.closest(".dropdown")) $$(".dropdown.open").forEach(function (x) { x.classList.remove("open"); }); });
  doc.addEventListener("keydown", function (e) { if (e.key === "Escape") { $$(".dropdown.open").forEach(function (x) { x.classList.remove("open"); }); closeModal(); } });

  /* ---------- notification bell ---------- */
  function loadNotifications() {
    var list = $("#bell-list"); if (!list) return;
    fetch("/notifications/latest/", { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } }).then(function (r) { return r.json(); }).then(function (d) {
      setCount($("#bell-count"), d.unread); list.innerHTML = "";
      if (!d.items.length) { list.innerHTML = '<p class="muted small" style="padding:12px">No notifications yet.</p>'; return; }
      d.items.forEach(function (n) {
        var a = doc.createElement("a"); a.href = n.open_url; a.className = "notif-item" + (n.is_read ? "" : " unread");
        var t = doc.createElement("strong"); t.textContent = n.title; var m = doc.createElement("small"); m.textContent = n.when + (n.message ? " · " + n.message : "");
        a.appendChild(t); a.appendChild(m); list.appendChild(a);
      });
    }).catch(function () {});
  }

  /* ---------- hero slider ---------- */
  var hero = $("[data-slider]");
  if (hero) {
    var track = $(".slides", hero), slides = $$(".slide", hero), dots = $$(".hero-dots button", hero), idx = 0, timer = null;
    function go(i) { idx = (i + slides.length) % slides.length; track.style.transform = "translateX(-" + idx * 100 + "%)"; dots.forEach(function (d, k) { d.setAttribute("aria-current", String(k === idx)); }); slides.forEach(function (s, k) { s.setAttribute("aria-hidden", String(k !== idx)); }); }
    function play() { if (reduceMotion || slides.length < 2) return; stop(); timer = setInterval(function () { go(idx + 1); }, 6500); }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    dots.forEach(function (d, k) { d.addEventListener("click", function () { go(k); play(); }); });
    var p = $(".hero-arrow.prev", hero), n = $(".hero-arrow.next", hero);
    if (p) p.addEventListener("click", function () { go(idx - 1); play(); }); if (n) n.addEventListener("click", function () { go(idx + 1); play(); });
    hero.addEventListener("mouseenter", stop); hero.addEventListener("mouseleave", play); hero.addEventListener("focusin", stop); hero.addEventListener("focusout", play);
    var sx = null; hero.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    hero.addEventListener("touchend", function (e) { if (sx === null) return; var dx = e.changedTouches[0].clientX - sx; if (Math.abs(dx) > 50) { go(idx + (dx < 0 ? 1 : -1)); play(); } sx = null; });
    go(0); play();
  }

  /* ---------- scroll-triggered animations ----------
     Cards, sections and banners on every public page get an entrance animation automatically; templates can
     still pick a direction with data-anim="left|right|bottom|top|scale|zoom|tl|tr|bl|br". Elements animate in
     each time they scroll into view (and quietly reset when they leave), using IntersectionObserver only. */
  var AUTO_SELECTOR = ".section-head, .why, .testi, .promo, .newsletter, .stat, .card, .pcard, .cat-tile, .line, .table-wrap, .review, .empty, .trust .container > div, .doc-section, .contact-card";
  $$(AUTO_SELECTOR).forEach(function (el) { if (!el.closest(".dash, .modal, .dropdown-panel, .rte") && !el.hasAttribute("data-anim") && !el.matches(".summary")) el.setAttribute("data-anim", "auto"); });
  var animEls = $$("[data-anim]");
  if (animEls.length) {
    if (reduceMotion || !("IntersectionObserver" in window)) { animEls.forEach(function (el) { el.classList.add("in-view"); }); }
    else {
      var PATTERN = ["left", "bottom", "right", "scale", "tl", "br", "tr", "bl"], SIMPLE = ["bottom", "left", "right", "zoom"];
      var byParent = new Map();
      animEls.forEach(function (el) { if (el.getAttribute("data-anim") === "auto") { var l = byParent.get(el.parentElement) || []; l.push(el); byParent.set(el.parentElement, l); } });
      byParent.forEach(function (list, parent) {
        var grouped = parent && parent.hasAttribute("data-anim-group"), set = grouped ? PATTERN : SIMPLE, off = grouped ? (parseInt(parent.getAttribute("data-anim-group"), 10) || 0) : 0;
        list.forEach(function (el, i) { el.setAttribute("data-anim", list.length === 1 ? "bottom" : set[(i + off) % set.length]); el.style.setProperty("--fd", (Math.random() * 2).toFixed(2) + "s"); });
      });
      var io = new IntersectionObserver(function (entries) {
        var entering = [];
        entries.forEach(function (e) {
          var big = e.rootBounds && e.intersectionRect.height >= e.rootBounds.height * 0.4; // very tall blocks
          if (e.isIntersecting && (e.intersectionRatio >= 0.12 || big)) { if (!e.target.classList.contains("in-view")) entering.push(e.target); }
          else if (!e.isIntersecting) { e.target.classList.remove("in-view"); }
        });
        entering.sort(function (a, b) { var A = a.getBoundingClientRect(), B = b.getBoundingClientRect(); return (A.top - B.top) || (A.left - B.left); });
        entering.forEach(function (el, i) { el.style.setProperty("--d", Math.min(i, 6) * 90 + "ms"); el.classList.add("in-view"); });
      }, { threshold: [0, 0.12], rootMargin: "0px 0px -5% 0px" });
      animEls.forEach(function (el) { if (el.getAttribute("data-anim") === "auto") el.setAttribute("data-anim", "bottom"); io.observe(el); });
    }
  }

  /* ---------- shop filters: auto-apply selects, close the price panel on outside click ---------- */
  var filterForm = $("#filter-form");
  if (filterForm) {
    $$("select", filterForm).forEach(function (sel) { sel.addEventListener("change", function () { filterForm.requestSubmit ? filterForm.requestSubmit() : filterForm.submit(); }); });
    doc.addEventListener("click", function (e) { $$("details.fdrop[open]").forEach(function (d) { if (!d.contains(e.target)) d.removeAttribute("open"); }); });
    doc.addEventListener("keydown", function (e) { if (e.key === "Escape") $$("details.fdrop[open]").forEach(function (d) { d.removeAttribute("open"); }); });
  }

  /* ---------- cart & wishlist (AJAX with graceful form fallback) ---------- */
  doc.addEventListener("submit", function (e) {
    var f = e.target;
    if (f.matches("[data-ajax-cart]")) {
      e.preventDefault(); var data = {}; new FormData(f).forEach(function (v, k) { data[k] = v; });
      post(f.action, data).then(function (r) {
        if (r.status === 401 && r.login_url) { window.location = r.login_url; return; }
        toast(r.message || (r.ok ? "Added to cart." : "Something went wrong."), r.ok ? "success" : "error");
        if (r.ok) setCount($("#cart-count"), r.count);
      }).catch(function () { f.submit(); });
    } else if (f.matches("[data-ajax-wish]")) {
      e.preventDefault(); var d2 = {}; new FormData(f).forEach(function (v, k) { d2[k] = v; });
      post(f.action, d2).then(function (r) {
        if (r.status === 401 && r.login_url) { window.location = r.login_url; return; }
        var btn = $("button", f); if (r.ok && btn) { btn.classList.toggle("on", r.in_wishlist); btn.setAttribute("aria-pressed", String(r.in_wishlist)); }
        toast(r.message || "Done", r.ok ? "success" : "error");
      }).catch(function () { f.submit(); });
    }
  });
  doc.addEventListener("click", function (e) {
    var c = e.target.closest("[data-confirm]"); if (c && !window.confirm(c.getAttribute("data-confirm"))) { e.preventDefault(); e.stopPropagation(); }
  }, true);

  /* ---------- quantity steppers ---------- */
  doc.addEventListener("click", function (e) {
    var b = e.target.closest("[data-qty]"); if (!b) return;
    var input = $("input", b.closest(".qty")); var step = parseInt(b.getAttribute("data-qty"), 10); var min = parseInt(input.min || "1", 10); var max = parseInt(input.max || "999", 10);
    var v = Math.max(min, Math.min(max, (parseInt(input.value, 10) || min) + step)); input.value = v;
    if (input.hasAttribute("data-autosubmit")) input.form.requestSubmit ? input.form.requestSubmit() : input.form.submit();
  });
  $$("input[data-autosubmit]").forEach(function (i) { i.addEventListener("change", function () { i.form.requestSubmit ? i.form.requestSubmit() : i.form.submit(); }); });
  $$("[data-sync-qty]").forEach(function (src) { src.addEventListener("input", function () { $$("[data-qty-target]").forEach(function (t) { t.value = src.value; }); }); });

  /* ---------- product gallery ---------- */
  $$("[data-gallery]").forEach(function (g) {
    var main = $(".main img", g);
    $$(".thumbs button", g).forEach(function (b) { b.addEventListener("click", function () { main.src = b.getAttribute("data-src"); $$(".thumbs button", g).forEach(function (x) { x.setAttribute("aria-current", "false"); }); b.setAttribute("aria-current", "true"); }); });
  });

  /* ---------- quick view modal ---------- */
  var modal = $("#quick-modal"), modalBody = modal ? $(".modal-content", modal) : null, lastFocus = null;
  function closeModal() { if (modal && modal.classList.contains("open")) { modal.classList.remove("open"); if (lastFocus) lastFocus.focus(); } }
  doc.addEventListener("click", function (e) {
    var q = e.target.closest("[data-quick]");
    if (q && modal) {
      e.preventDefault(); lastFocus = q; modalBody.innerHTML = '<p class="muted center">Loading…</p>'; modal.classList.add("open");
      fetch(q.getAttribute("data-quick"), { credentials: "same-origin" }).then(function (r) { return r.text(); }).then(function (h) { modalBody.innerHTML = h; var cl = $(".modal-close", modal); if (cl) cl.focus(); }).catch(function () { modalBody.innerHTML = '<p class="muted">Could not load this product.</p>'; });
    }
    if (e.target.closest("[data-modal-close]") || e.target === modal) closeModal();
  });

  /* ---------- copy / share ---------- */
  doc.addEventListener("click", function (e) {
    var c = e.target.closest("[data-copy]"); if (!c) return;
    var text = c.getAttribute("data-copy");
    (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(function () { toast("Copied!"); }).catch(function () {
      var t = doc.createElement("textarea"); t.value = text; doc.body.appendChild(t); t.select(); try { doc.execCommand("copy"); toast("Copied!"); } catch (er) { toast("Press Ctrl+C to copy", "warning"); } t.remove();
    });
  });
})();
