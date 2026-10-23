"""Confluence storage-format HTML to plain text, with the standard library only.

Keeps what retrieval needs: headings as Markdown-style lines, paragraphs and list
items on their own lines, code blocks fenced, table rows as " | "-joined cells.
Drops scripts, styles and Confluence macro parameters.
"""
from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

_BLOCK = {"p", "div", "li", "tr", "br", "section", "blockquote", "ul", "ol", "table", "dl", "dt", "dd"}
_HEADINGS = {"h1": "#", "h2": "##", "h3": "###", "h4": "####", "h5": "#####", "h6": "######"}
_SKIP = {"script", "style", "ac:parameter", "nav", "header", "footer"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0
        self._pre = 0
        self._cells: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip += 1
        elif tag in ("pre", "ac:plain-text-body"):
            self._pre += 1
            self.out.append("\n```\n")
        elif tag in _HEADINGS:
            self.out.append("\n\n" + _HEADINGS[tag] + " ")
        elif tag == "tr":
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._cell = []
        elif tag in _BLOCK:
            self.out.append("\n")
            if tag == "li":
                self.out.append("- ")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in ("pre", "ac:plain-text-body"):
            self._pre = max(0, self._pre - 1)
            self.out.append("\n```\n")
        elif tag in ("td", "th") and self._cell is not None and self._cells is not None:
            self._cells.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._cells is not None:
            self.out.append("\n" + " | ".join(c for c in self._cells if c) + "\n")
            self._cells = None
        elif tag in _HEADINGS or tag in _BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
        else:
            self.out.append(data)


def html_to_text(html: str) -> str:
    parser = _Extractor()
    parser.feed(html or "")
    parser.close()
    text = unescape("".join(parser.out))
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
