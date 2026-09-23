#!/usr/bin/env python3
"""Checks the built site before every merge. Exit status is non-zero on any failure.

    NOVENA_REPO=../novena python3 tools/check.py

1. privacy.html is byte-identical to the app repository's site/privacy.html.
2. Nothing is loaded from another host: no absolute URL in any src, srcset,
   stylesheet/icon/preload link, CSS url(), import, or script. Plain <a href>
   links to other sites are navigation, not loads, and are allowed.
3. No text from a paid novena appears anywhere on the site.
4. Every free novena has a page, and its source line is the novena's `source`.
5. Every relative link and asset resolves to a file in this repository.
6. No cookie, form, input, iframe, embed, object or script (other than JSON-LD).
"""
from __future__ import annotations

import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
APP = Path(os.environ.get("NOVENA_REPO", ROOT.parent / "novena")).resolve()
LANG_FILES = {"en": "", "es": ".es", "pt-BR": ".pt-BR", "it": ".it", "fil": ".fil"}
LANG_PREFIX = {"en": "", "es": "es/", "pt-BR": "pt-br/", "it": "it/", "fil": "fil/"}

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


class Scan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.loads: list[str] = []
        self.links: list[str] = []
        self.forbidden: list[str] = []
        self.text: list[str] = []
        self._script_type: str | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("iframe", "embed", "object", "form", "input", "textarea", "select", "button", "video", "audio"):
            self.forbidden.append(tag)
        if tag == "script":
            if a.get("type") != "application/ld+json" or a.get("src"):
                self.forbidden.append("script")
            self._script_type = a.get("type")
        if tag == "meta" and (a.get("http-equiv") or "").lower() == "set-cookie":
            self.forbidden.append("set-cookie")
        for k in ("src", "srcset", "poster", "data"):
            if a.get(k):
                self.loads.append(a[k])
        if tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel in ("canonical", "alternate"):
                pass  # identifiers, never fetched by a browser
            elif a.get("href"):
                self.loads.append(a["href"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "meta" and a.get("property") == "og:image":
            pass  # read by link-preview crawlers only, never by a visitor's browser

    def handle_endtag(self, tag):
        if tag == "script":
            self._script_type = None

    def handle_data(self, data):
        self.text.append(data)


def is_remote(u: str) -> bool:
    """True for anything a browser would fetch from somewhere other than this site."""
    u = u.strip()
    if u.startswith("//"):
        return True
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", u)
    return bool(m) and m.group(1).lower() != "data"


def resolve(page: Path, href: str) -> Path | None:
    p = urlparse(href)
    if p.scheme or p.netloc or href.startswith(("mailto:", "#")):
        return None
    path = unquote(p.path)
    if not path:
        return None
    if path.startswith("/"):
        # Root-absolute paths are only used by 404.html; strip the site root.
        base = urlparse(os.environ.get("BASE_URL", "https://getnovena.app/")).path
        path = path[len(base):] if path.startswith(base) else path.lstrip("/")
        target = ROOT / path
    else:
        target = (page.parent / path)
    target = target.resolve()
    if target.is_dir() or path.endswith("/"):
        target = target / "index.html"
    return target


def main() -> None:
    # 1. privacy
    ours = (ROOT / "privacy.html").read_bytes()
    theirs = (APP / "site/privacy.html").read_bytes()
    if ours != theirs:
        fail("privacy.html differs from kipster254/novena site/privacy.html")

    pages = sorted(p for p in ROOT.rglob("*.html") if "tools" not in p.parts and ".git" not in p.parts)
    all_text = {}
    for page in pages:
        if page.name == "privacy.html":
            continue
        html = page.read_text("utf-8")
        s = Scan()
        s.feed(html)
        rp = page.relative_to(ROOT)
        for u in s.loads:
            if is_remote(u):
                fail(f"{rp}: loads from another host: {u}")
            else:
                t = resolve(page, u)
                if t and not t.exists():
                    fail(f"{rp}: missing asset {u}")
        for u in s.links:
            t = resolve(page, u)
            if t and not t.exists():
                fail(f"{rp}: broken link {u}")
        for f in s.forbidden:
            fail(f"{rp}: forbidden element or header: {f}")
        all_text[rp] = re.sub(r"\s+", " ", " ".join(s.text))

    # 2b. CSS
    for css in ROOT.rglob("*.css"):
        body = css.read_text("utf-8")
        for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)", body):
            u = m.group(1)
            if is_remote(u):
                fail(f"{css.relative_to(ROOT)}: loads from another host: {u}")
            elif not (css.parent / u).exists():
                fail(f"{css.relative_to(ROOT)}: missing {u}")
        if "@import" in body:
            fail(f"{css.relative_to(ROOT)}: @import is not allowed")

    # 3 & 4. content
    site_text = " ".join(all_text.values())
    langs = [l for l in LANG_FILES if (ROOT / LANG_PREFIX[l] / "novenas").is_dir() and (l == "en" or LANG_PREFIX[l])]
    for lang in langs:
        cat = json.loads((APP / "src/data" / f"novenas{LANG_FILES[lang]}.json").read_text("utf-8"))["novenas"]
        for n in cat:
            pieces = [n["opening_prayer"]] + [d["body_text"] for d in n["days"]] + [d["closing_prayer"] for d in n["days"]]
            page = ROOT / LANG_PREFIX[lang] / "novenas" / n["id"].removeprefix("novena-") / "index.html"
            if not page.exists():
                fail(f"{lang}: no page for {n['id']}")
                continue
            if n["is_free"]:
                text = all_text[page.relative_to(ROOT)]
                for piece in pieces:
                    first = re.sub(r"\s+", " ", piece.strip().split("\n")[0])[:120]
                    if first not in text:
                        fail(f"{lang}/{n['id']}: free text missing from its page: {first[:50]}…")
                if re.sub(r"\s+", " ", n["source"]) not in text:
                    fail(f"{lang}/{n['id']}: source line does not match the novena's source field")
            else:
                for piece in pieces:
                    # Short shared formulas ("Glory be…", "Our Father…") appear in
                    # free novenas too; check only distinctive runs of 80+ chars.
                    for chunk in re.split(r"(?<=[.!?])\s+", piece):
                        chunk = re.sub(r"\s+", " ", chunk.strip())
                        if len(chunk) >= 80 and chunk in site_text:
                            owners = [str(k) for k, v in all_text.items() if chunk in v]
                            free_has = any(chunk in re.sub(r"\s+", " ", x["opening_prayer"] + " ".join(d["body_text"] + " " + d["closing_prayer"] for d in x["days"])) for x in cat if x["is_free"])
                            if not free_has:
                                fail(f"{lang}/{n['id']}: PAID TEXT on {owners[:2]}: {chunk[:60]}…")

    # sitemap URLs exist
    base = os.environ.get("BASE_URL", "https://getnovena.app/")
    for loc in re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text("utf-8")):
        if not loc.startswith(base):
            fail(f"sitemap: {loc} is not under {base}")
            continue
        t = resolve(ROOT / "index.html", loc[len(base):] or "./")
        if t and not t.exists():
            fail(f"sitemap: {loc} has no file")

    if failures:
        print("FAIL")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print(f"OK: {len(pages)} pages; privacy identical; no third-party loads; no paid text; links resolve.")


if __name__ == "__main__":
    main()
