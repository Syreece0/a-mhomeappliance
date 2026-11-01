"""Allow-list HTML sanitizer for admin-edited page content (standard library only).

The admin writes content in a visual editor, but the browser can still be tricked into sending anything
(pasted markup, a hand-crafted request). Everything is therefore cleaned on the server before it is saved:
only the tags below survive, every attribute is dropped except safe link targets, and script/style content
is removed entirely.
"""
import re
from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    "p", "br", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "ul", "ol", "li", "a", "blockquote", "hr",
    "table", "thead", "tbody", "tr", "th", "td",
}
SELF_CLOSING = {"br", "hr"}
BLOCKS = {"p", "ul", "ol", "h2", "h3", "h4", "blockquote", "table", "hr"}  # cannot sit inside a <p>
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "noscript", "template", "svg", "math", "head", "title"}
# editors sometimes produce these; map them to what we allow
RENAME = {"h1": "h2", "h5": "h4", "h6": "h4", "div": "p", "strike": "u", "del": "u"}
SAFE_URL = re.compile(r"^(https?://|mailto:|tel:|/|#)", re.I)
MAX_BODY_CHARS = 40000


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.stack = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if self.skip_depth:
            if tag in DROP_CONTENT:
                self.skip_depth += 1
            return
        if tag in DROP_CONTENT:
            self.skip_depth = 1
            return
        tag = RENAME.get(tag, tag)
        if tag not in ALLOWED_TAGS:
            return
        if tag in BLOCKS and "p" in self.stack:  # <p><ul>..</ul></p> is invalid: end the paragraph first
            while self.stack:
                top = self.stack.pop()
                self.out.append(f"</{top}>")
                if top == "p":
                    break
        if tag == "li" and self.stack and self.stack[-1] == "li":  # <li>a<li>b -> two items, not nested
            self.stack.pop()
            self.out.append("</li>")
        if tag in SELF_CLOSING:
            self.out.append(f"<{tag}>")
            return
        if tag == "a":
            href = ""
            for k, v in attrs:
                if k == "href" and v and SAFE_URL.match(v.strip()):
                    href = v.strip()
            if href:
                self.out.append(f'<a href="{escape(href, quote=True)}" rel="noopener nofollow">')
            else:
                self.out.append("<a>")
        else:
            self.out.append(f"<{tag}>")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.skip_depth:
            if tag in DROP_CONTENT:
                self.skip_depth -= 1
            return
        tag = RENAME.get(tag, tag)
        if tag in SELF_CLOSING or tag not in ALLOWED_TAGS or tag not in self.stack:
            return
        while self.stack:  # close anything left open inside it, so tags always nest correctly
            top = self.stack.pop()
            self.out.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        if not self.skip_depth:
            self.out.append(escape(data, quote=False))

    def close(self):
        super().close()
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")


def sanitize_html(html):
    """Return a safe, well-nested version of `html`."""
    html = (html or "")[: MAX_BODY_CHARS * 3]
    cleaner = _Cleaner()
    cleaner.feed(html)
    cleaner.close()
    text = "".join(cleaner.out)
    text = re.sub(r"<a>(.*?)</a>", r"\1", text, flags=re.S)  # links with no usable target become plain text
    text = re.sub(r"<(p|h2|h3|h4|li|strong|em|b|i|u)>\s*(<br>\s*)*</\1>", "", text)  # drop empty blocks
    text = re.sub(r"(\s*<br>\s*){3,}", "<br><br>", text)
    return text.strip()


def plain_text(html):
    """Readable plain text of sanitized html (used for search/summaries)."""
    text = re.sub(r"<(br|/p|/h[2-4]|/li|/tr)>", " ", html or "")
    text = re.sub(r"<[^>]+>", "", text)
    from html import unescape

    return re.sub(r"\s+", " ", unescape(text)).strip()
