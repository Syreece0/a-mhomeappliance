/* Lightweight visual editor for admin content. Upgrades <textarea data-richtext> to a formatting toolbar +
   editable area and keeps the textarea in sync. Without JavaScript the plain textarea still works, and the
   server sanitises whatever is submitted, so this script is a convenience, not a security boundary. */
(function () {
  "use strict";
  var doc = document;

  function button(label, title, onClick, extraClass) {
    var b = doc.createElement("button");
    b.type = "button"; b.className = "rte-btn" + (extraClass ? " " + extraClass : "");
    b.innerHTML = label; b.title = title; b.setAttribute("aria-label", title);
    b.addEventListener("mousedown", function (e) { e.preventDefault(); }); // keep the text selection
    b.addEventListener("click", onClick);
    return b;
  }

  function init(ta) {
    var wrap = doc.createElement("div"); wrap.className = "rte";
    var bar = doc.createElement("div"); bar.className = "rte-bar"; bar.setAttribute("role", "toolbar"); bar.setAttribute("aria-label", "Formatting");
    var area = doc.createElement("div"); area.className = "rte-area prose"; area.contentEditable = "true";
    area.setAttribute("role", "textbox"); area.setAttribute("aria-multiline", "true");
    var label = doc.querySelector('label[for="' + ta.id + '"]'); if (label) area.setAttribute("aria-label", label.textContent);
    area.innerHTML = ta.value;
    try { doc.execCommand("defaultParagraphSeparator", false, "div"); } catch (e) {}
    var tokens = []; try { tokens = JSON.parse(ta.getAttribute("data-tokens") || "[]"); } catch (e) {}

    function sync() { ta.value = area.innerHTML; }
    var lastRange = null; // remembered so toolbar dropdowns (which take focus) can still insert at the caret
    function remember() { var s = window.getSelection(); if (s.rangeCount && area.contains(s.anchorNode)) lastRange = s.getRangeAt(0).cloneRange(); }
    ["keyup", "mouseup", "input", "focusout"].forEach(function (ev) { area.addEventListener(ev, remember); });
    function inBlock() {
      var n = window.getSelection().anchorNode;
      while (n && n !== area) { if (n.nodeType === 1 && /^(DIV|P|LI|H[1-6]|BLOCKQUOTE|TD|TH)$/.test(n.nodeName)) return true; n = n.parentNode; }
      return false;
    }
    // caret position as "characters of text before it" - survives the browser replacing text nodes
    function caretOffset() {
      var sel = window.getSelection();
      if (!sel.rangeCount || !sel.isCollapsed || !area.contains(sel.anchorNode)) return null;
      var r = doc.createRange(); r.selectNodeContents(area); r.setEnd(sel.anchorNode, sel.anchorOffset);
      return r.toString().length;
    }
    function setCaretOffset(n) {
      var w = doc.createTreeWalker(area, NodeFilter.SHOW_TEXT), node, left = n;
      while ((node = w.nextNode())) {
        if (left <= node.length) { var r = doc.createRange(); r.setStart(node, left); r.collapse(true); var s = window.getSelection(); s.removeAllRanges(); s.addRange(r); return; }
        left -= node.length;
      }
    }
    function cmd(name, value) {
      if (doc.activeElement !== area) { area.focus(); if (lastRange) { var s0 = window.getSelection(); s0.removeAllRanges(); s0.addRange(lastRange); } }
      if (!inBlock()) { // text must always live in a block (e.g. after Select All + Delete)
        var off = caretOffset(); area.innerHTML = "<div>" + (area.innerHTML.replace(/<\/?span[^>]*>/g, "") || "<br>") + "</div>"; if (off !== null) setCaretOffset(off);
      }
      var keep = caretOffset();
      doc.execCommand(name, false, value || null);
      if (keep !== null) setCaretOffset(keep); // browsers jump to the start after a list command
      remember(); sync();
    }

    var block = doc.createElement("select"); block.className = "rte-select"; block.setAttribute("aria-label", "Text style");
    [["p", "Paragraph"], ["h2", "Heading"], ["h3", "Sub-heading"]].forEach(function (o) { var op = doc.createElement("option"); op.value = o[0]; op.textContent = o[1]; block.appendChild(op); });
    block.addEventListener("change", function () { cmd("formatBlock", "<" + block.value + ">"); });
    bar.appendChild(block);

    bar.appendChild(button("<b>B</b>", "Bold", function () { cmd("bold"); }));
    bar.appendChild(button("<i>I</i>", "Italic", function () { cmd("italic"); }));
    bar.appendChild(button("&bull; List", "Bulleted list", function () { cmd("insertUnorderedList"); }));
    bar.appendChild(button("1. List", "Numbered list", function () { cmd("insertOrderedList"); }));
    bar.appendChild(button("Link", "Add a link", function () {
      var url = window.prompt("Link address (https://..., mailto:..., or /page/):", "https://");
      if (url && /^(https?:\/\/|mailto:|tel:|\/|#)/i.test(url.trim())) cmd("createLink", url.trim());
      else if (url) window.alert("Please enter an address starting with https://, mailto:, tel: or /");
    }));
    bar.appendChild(button("Unlink", "Remove link", function () { cmd("unlink"); }));
    bar.appendChild(button("Clear", "Clear formatting", function () { cmd("removeFormat"); cmd("formatBlock", "<p>"); }));

    if (tokens.length) {
      var ins = doc.createElement("select"); ins.className = "rte-select"; ins.setAttribute("aria-label", "Insert a live business detail");
      var first = doc.createElement("option"); first.value = ""; first.textContent = "Insert detail…"; ins.appendChild(first);
      tokens.forEach(function (t) { var op = doc.createElement("option"); op.value = t[0]; op.textContent = t[1]; ins.appendChild(op); });
      ins.addEventListener("change", function () { if (ins.value) { cmd("insertText", "{{" + ins.value + "}}"); ins.value = ""; } });
      bar.appendChild(ins);
    }

    // paste as plain text so pasted web pages / Word documents cannot bring in stray styles
    area.addEventListener("paste", function (e) {
      e.preventDefault();
      var text = (e.clipboardData || window.clipboardData).getData("text/plain");
      doc.execCommand("insertText", false, text); sync();
    });
    area.addEventListener("input", sync);
    area.addEventListener("keyup", function () {
      var sel = window.getSelection(); if (!sel.rangeCount) return;
      var n = sel.anchorNode; while (n && n !== area) { if (n.nodeType === 1 && /^H[23]$/.test(n.nodeName)) { block.value = n.nodeName.toLowerCase(); return; } n = n.parentNode; }
      block.value = "p";
    });

    ta.style.display = "none";
    ta.parentNode.insertBefore(wrap, ta); wrap.appendChild(bar); wrap.appendChild(area); wrap.appendChild(ta);
    if (ta.form) ta.form.addEventListener("submit", sync);
    try { doc.execCommand("styleWithCSS", false, false); doc.execCommand("defaultParagraphSeparator", false, "div"); } catch (e) {} // <div> blocks nest lists correctly; the server turns them into <p>
  }

  Array.prototype.forEach.call(doc.querySelectorAll("textarea[data-richtext]"), init);
})();
