#!/usr/bin/env python3
"""Builds the static getnovena.app site from the app's own content files.

    NOVENA_REPO=../novena python3 tools/build.py

Reads the catalog from a checkout of kipster254/novena (never copied into this
repository — the paid novenas' text must not be published, and a copy of the
JSON here would publish it). Writes plain HTML into this repository's root.

Rules this script enforces rather than trusts:
  * Full text is written only for novenas with `is_free: true` in the shipped
    catalog of that language. Every other novena gets a summary page: title,
    who it is prayed to, intentions, and its source note. Never a prayer.
  * The source line printed on a page is the novena's own `source` field, the
    same string the app renders under Sources.
  * privacy.html is never written. It is the Play-held policy and is copied
    from the app repository's site/ by hand, byte for byte.
  * Nothing is loaded from any host but this site.
"""
from __future__ import annotations

import html
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent))
from strings import STRINGS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = Path(os.environ.get("NOVENA_REPO", ROOT.parent / "novena")).resolve()

# ---------------------------------------------------------------------------
# Configuration. The two switches a launch flips live here.
# ---------------------------------------------------------------------------

# Where the site is served. Canonical URLs, the sitemap and Open Graph tags are
# absolute and use this. It stays on github.io until the cutover PR, which
# changes this one line and adds CNAME in the same commit.
BASE_URL = os.environ.get("BASE_URL", "https://kipster254.github.io/novena-site/")

# False until Google Play production access is granted and the listing is
# public. While False, no page links to Play: each shows a "coming soon" state.
PLAY_LIVE = os.environ.get("PLAY_LIVE", "0") == "1"

PACKAGE = "com.arapleting.novena"

# Languages built. English only on main; each other language is added on its
# own branch and merged only after a native reader has signed it off.
LANGS = [l for l in os.environ.get("LANGS", "en").split(",") if l]

LANG_FILES = {"en": "", "es": ".es", "pt-BR": ".pt-BR", "it": ".it", "fil": ".fil"}
# URL prefix per language. English is the root.
LANG_PREFIX = {"en": "", "es": "es/", "pt-BR": "pt-br/", "it": "it/", "fil": "fil/"}
HREFLANG = {"en": "en", "es": "es", "pt-BR": "pt-BR", "it": "it", "fil": "fil"}

BUILD_DATE = os.environ.get("BUILD_DATE", date.today().isoformat())


def play_url(campaign: str, content: str | None = None, lang: str = "en") -> str:
    """Google Play listing URL carrying UTM parameters in `referrer`.

    Play reads utm_* values from the url-encoded `referrer` parameter and shows
    them in Play Console's acquisition reporting. Nothing about the visitor is
    sent anywhere by following this link other than what any link to Play sends.
    """
    ref = f"utm_source=getnovena.app&utm_medium=website&utm_campaign={campaign}"
    if content:
        ref += f"&utm_content={content}"
    hl = {"en": "en", "es": "es", "pt-BR": "pt-BR", "it": "it", "fil": "fil"}[lang]
    return (
        f"https://play.google.com/store/apps/details?id={PACKAGE}&hl={hl}"
        f"&referrer={quote(ref, safe='')}"
    )


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------

def load(lang: str) -> dict:
    suffix = LANG_FILES[lang]
    data = APP / "src" / "data"
    novenas = json.loads((data / f"novenas{suffix}.json").read_text("utf-8"))
    saints = json.loads((data / f"saints{suffix}.json").read_text("utf-8"))
    intentions = json.loads((data / f"intentions{suffix}.json").read_text("utf-8"))
    return {
        "version": novenas["content_version"],
        "novenas": novenas["novenas"],
        "saints": {s["id"]: s for s in saints["saints"]},
        "intentions": {i["id"]: i["label"] for i in intentions["intentions"]},
    }


def slug(novena_id: str) -> str:
    return novena_id.removeprefix("novena-")


def e(text: str) -> str:
    return html.escape(text, quote=True)


def paras(text: str) -> str:
    return "".join(f"<p>{e(p.strip())}</p>" for p in text.split("\n") if p.strip())


# Disclosures the app itself shows beside these two titles (composition.*
# in the app's interface strings). Printed verbatim beside the title.
COMPOSITION_KEY = {"novena-divine-mercy": "mercy", "novena-surrender": "surrender"}


def composition_notice(lang: str, novena_id: str) -> str | None:
    key = COMPOSITION_KEY.get(novena_id)
    if not key:
        return None
    res = json.loads((APP / "src/lib/i18n/resources" / f"{lang}.json").read_text("utf-8"))
    return res["composition"][key]


MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
           "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
    "pt-BR": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
              "agosto", "setembro", "outubro", "novembro", "dezembro"],
}
ENDONYM = {"en": "English", "es": "Español", "pt-BR": "Português (Brasil)", "it": "Italiano", "fil": "Filipino"}


def month_day(mmdd: str, lang: str) -> str:
    m, d = (int(x) for x in mmdd.split("-"))
    names = MONTHS.get(lang, MONTHS["en"])
    if lang == "en":
        return f"{names[m - 1]} {d}"
    return f"{d} de {names[m - 1]}" if lang in ("es", "pt-BR") else f"{d} {names[m - 1]}"


# ---------------------------------------------------------------------------
# Page shell
# ---------------------------------------------------------------------------

def rel(depth: int) -> str:
    return "../" * depth if depth else "./"


def page(*, lang: str, path: str, title: str, description: str, body: str,
         depth: int, og_image: str = "assets/img/og-default.png",
         jsonld: dict | None = None, alternates: dict[str, str] | None = None,
         noindex: bool = False) -> str:
    s = STRINGS[lang]
    r = rel(depth)
    canonical = BASE_URL + path
    alt_links = ""
    if alternates:
        for l, p in alternates.items():
            alt_links += f'<link rel="alternate" hreflang="{HREFLANG[l]}" href="{BASE_URL}{p}">\n'
        if "en" in alternates:
            alt_links += f'<link rel="alternate" hreflang="x-default" href="{BASE_URL}{alternates["en"]}">\n'
    ld = ""
    if jsonld:
        ld = ('<script type="application/ld+json">'
              + json.dumps(jsonld, ensure_ascii=False).replace("</", "<\\/")
              + "</script>\n")
    home = r + LANG_PREFIX[lang]
    nov = home + "novenas/"
    robots = '<meta name="robots" content="noindex">\n' if noindex else ""
    others = [l for l in LANGS if l != lang]
    lang_links = ('<p class="langs">' + " · ".join(
        f'<a href="{r}{LANG_PREFIX[l]}" hreflang="{HREFLANG[l]}" lang="{HREFLANG[l]}">{ENDONYM[l]}</a>'
        for l in others) + "</p>") if others else ""
    return f"""<!doctype html>
<html lang="{s['html_lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; script-src 'none'; connect-src 'none'; form-action 'none'; base-uri 'none'">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#F7F3EA" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#101426" media="(prefers-color-scheme: dark)">
{robots}<link rel="canonical" href="{canonical}">
{alt_links}<link rel="icon" href="{r}assets/img/icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="{r}assets/img/icon-192.png">
<link rel="preload" href="{r}assets/fonts/newsreader-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{r}assets/site.css">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Novena">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{BASE_URL}{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="{s['og_locale']}">
<meta name="twitter:card" content="summary_large_image">
{ld}</head>
<body>
<a class="skip" href="#main">{e(s['skip'])}</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="wordmark" href="{home}">Novena</a>
    <nav aria-label="Site">
      <a href="{nov}">{e(s['nav_novenas'])}</a>
      <a href="{home}support/">{e(s['nav_support'])}</a>
      <a href="{home}press/">{e(s['nav_press'])}</a>
    </nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <nav aria-label="Footer">
      <a href="{nov}">{e(s['footer_novenas'])}</a>
      <a href="{home}what-is-a-novena/">{e(s['nav_guide'])}</a>
      <a href="{home}support/">{e(s['footer_support'])}</a>
      <a href="{home}press/">{e(s['footer_press'])}</a>
      <a href="{r}privacy.html">{e(s['footer_privacy'])}</a>
    </nav>
    {lang_links}
    <p>{e(s['not_affiliated'])}</p>
    {f"<p>{e(s['play_trademark'])}</p>" if PLAY_LIVE else ""}
    <p>{e(s['footer_no_tracking'])}</p>
  </div>
</footer>
</body>
</html>
"""


def store_block(lang: str, depth: int, campaign: str, content: str,
                heading: str | None = None, body: str | None = None) -> str:
    """The one place the site points at Google Play."""
    s = STRINGS[lang]
    r = rel(depth)
    head = f"<h2>{e(heading)}</h2>" if heading else ""
    lead = f"<p>{e(body)}</p>" if body else ""
    if PLAY_LIVE:
        badge = (f'<a class="play-badge" href="{e(play_url(campaign, content, lang))}" '
                 f'rel="noopener">'
                 f'<img class="{"padded" if lang == "en" else "bare"}" src="{r}assets/img/google-play-badge-{lang}.png" '
                 f'alt="{e(s["get_it"])}" width="646" height="250"></a>')
        return f'<div class="store">{head}{lead}{badge}</div>'
    return (f'<div class="store">{head}{lead}'
            f'<p class="coming"><strong>{e(s["coming_soon"])}.</strong> '
            f'{e(s["coming_soon_body"])}</p></div>')


def app_jsonld(lang: str) -> dict:
    d = {
        "@context": "https://schema.org",
        "@type": "MobileApplication",
        "name": "Novena",
        "operatingSystem": "Android",
        "inLanguage": ["en", "es", "pt-BR", "it", "fil"],
        "description": STRINGS[lang]["press_one_sentence"],
        "url": BASE_URL,
        "image": BASE_URL + "assets/img/icon-512.png",
    }
    if PLAY_LIVE:
        d["installUrl"] = f"https://play.google.com/store/apps/details?id={PACKAGE}"
        d["sameAs"] = [f"https://play.google.com/store/apps/details?id={PACKAGE}"]
    return d


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def novena_card(lang: str, n: dict, c: dict, depth: int) -> str:
    s = STRINGS[lang]
    href = f"{rel(depth)}{LANG_PREFIX[lang]}novenas/{slug(n['id'])}/"
    saint = c["saints"].get(n["saint_id"], {})
    intents = ", ".join(c["intentions"][i] for i in n["intention_ids"] if i in c["intentions"])
    badge = (f'<span class="badge free">{e(s["badge_free"])}</span>' if n["is_free"]
             else f'<span class="badge">{e(s["badge_unlock"])}</span>')
    notice = composition_notice(lang, n["id"])
    note = f'<p class="disclosure">{e(notice)}</p>' if notice else ""
    return (f'<li class="card"><a href="{href}"><span class="card-title">{e(n["title"])}</span>'
            f'{badge}</a>{note}<p class="muted">{e(intents)}</p></li>')


def build_home(lang: str, c: dict) -> str:
    s = STRINGS[lang]
    depth = len(LANG_PREFIX[lang].strip("/").split("/")) if LANG_PREFIX[lang] else 0
    r = rel(depth)
    free = [n for n in c["novenas"] if n["is_free"]]
    jude = next((n for n in free if n["id"] == "novena-st-jude"), None)
    what = "".join(f"<p>{e(p)}</p>" for p in s["what_body"])
    promise = "".join(f"<li><h3>{e(h)}</h3><p>{e(b)}</p></li>" for h, b in s["promise_items"])
    free_list = "".join(novena_card(lang, n, c, depth) for n in free)
    shot_files = [("screen-today.png", 540, 500, 0), ("screen-2.png", 540, 960, 1)]
    shots = "".join(
        f'<figure><img src="{r}assets/img/{f}" alt="{e(s["shot_alts"][i])}" '
        f'width="{w}" height="{h}" loading="lazy"></figure>'
        for f, w, h, i in shot_files)
    try_jude = ""
    if jude:
        try_jude = (f'<p class="hero-try"><a class="button" href="{r}{LANG_PREFIX[lang]}novenas/st-jude/#day-1">'
                    f'{e(s["hero_try"])}</a><span class="muted">{e(s["hero_try_sub"])}</span></p>')
    body = f"""
<section class="hero">
  <div class="wrap">
    <p class="kicker">{e(s['hero_kicker'])}</p>
    <h1>{s['hero_line']}</h1>
    <p class="promise">{e(s['promise_line'])}</p>
    {try_jude}
    {store_block(lang, depth, 'site', 'home_hero')}
  </div>
</section>
<section class="wrap prose">
  <h2>{e(s['section_what'])}</h2>
  {what}
  <p><a href="{r}{LANG_PREFIX[lang]}what-is-a-novena/">{e(s['nav_guide'])} →</a></p>
</section>
<section class="wrap">
  <h2>{e(s['section_promise'])}</h2>
  <ul class="promises">{promise}</ul>
</section>
<section class="wrap">
  <h2>{e(s['section_free'])}</h2>
  <p>{e(s['free_intro'])}</p>
  <ul class="cards">{free_list}</ul>
  <p><a href="{r}{LANG_PREFIX[lang]}novenas/">{e(s['free_more'])} →</a></p>
</section>
<section class="wrap">
  <h2>{e(s['section_screens'])}</h2>
  <div class="shots">{shots}</div>
</section>
<section class="wrap prose">
  <h2>{e(s['section_languages'])}</h2>
  <p>{e(s['languages_body'])}</p>
  <h2>{e(s['section_honest'])}</h2>
  <p>{e(s['honest_body'])}</p>
</section>
<section class="wrap">
  {store_block(lang, depth, 'site', 'home_footer', s['cta_heading'], s['cta_body'])}
</section>
"""
    alternates = {l: LANG_PREFIX[l] for l in LANGS}
    return page(lang=lang, path=LANG_PREFIX[lang], title=s["home_title"],
                description=s["home_description"], body=body, depth=depth,
                jsonld=app_jsonld(lang), alternates=alternates)


def build_index(lang: str, c: dict) -> str:
    s = STRINGS[lang]
    depth = (1 if not LANG_PREFIX[lang] else 2)
    free = [n for n in c["novenas"] if n["is_free"]]
    rest = [n for n in c["novenas"] if not n["is_free"]]
    rest.sort(key=lambda n: n["title"])
    body = f"""
<section class="wrap">
  <h1>{e(s['novenas_title'])}</h1>
  <p class="lead">{e(s['novenas_intro'])}</p>
  <h2>{e(s['badge_free'])}</h2>
  <ul class="cards">{''.join(novena_card(lang, n, c, depth) for n in free)}</ul>
  <h2>{e(s['badge_unlock'])}</h2>
  <ul class="cards">{''.join(novena_card(lang, n, c, depth) for n in rest)}</ul>
</section>
"""
    path = LANG_PREFIX[lang] + "novenas/"
    return page(lang=lang, path=path, title=f"{s['novenas_title']} — Novena",
                description=s["novenas_description"], body=body, depth=depth,
                alternates={l: LANG_PREFIX[l] + "novenas/" for l in LANGS})


def meta_block(lang: str, n: dict, c: dict) -> str:
    s = STRINGS[lang]
    saint = c["saints"].get(n["saint_id"], {})
    intents = ", ".join(c["intentions"][i] for i in n["intention_ids"] if i in c["intentions"])
    rows = []
    if saint.get("name"):
        rows.append((s["saint_label"], e(saint["name"])))
    if intents:
        rows.append((s["for_label"], e(intents)))
    if n.get("is_fixed_date") and n.get("fixed_start_date"):
        rows.append((s["fixed_label"], e(month_day(n["fixed_start_date"], lang))))
    elif saint.get("feast_date"):
        rows.append((s["feast_label"], e(month_day(saint["feast_date"], lang))))
    return "<dl class=\"meta\">" + "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in rows) + "</dl>"


def source_block(lang: str, n: dict) -> str:
    s = STRINGS[lang]
    imp = ""
    if n.get("imprimatur_info"):
        imp = f'<p><strong>{e(s["imprimatur_label"])}:</strong> {e(n["imprimatur_info"])}</p>'
    return (f'<aside class="source" aria-label="{e(s["source_label"])}">'
            f'<h2>{e(s["about_source"])}</h2><p><strong>{e(s["source_label"])}:</strong> '
            f'{e(n["source"])}</p>{imp}</aside>')


def build_novena(lang: str, n: dict, c: dict) -> str:
    s = STRINGS[lang]
    depth = 2 if not LANG_PREFIX[lang] else 3
    sl = slug(n["id"])
    path = f"{LANG_PREFIX[lang]}novenas/{sl}/"
    saint = c["saints"].get(n["saint_id"], {})
    notice = composition_notice(lang, n["id"])
    disclosure = f'<p class="disclosure">{e(notice)}</p>' if notice else ""
    about = ""
    if saint.get("short_bio"):
        about = (f'<details class="about"><summary>{e(s["about_label"])} {e(saint["name"])}</summary>'
                 f'{paras(saint["short_bio"])}'
                 f'<p class="muted">{e(saint.get("source_attribution", ""))}</p></details>')

    if n["is_free"]:
        days_nav = "".join(f'<a href="#day-{d["day_number"]}">{d["day_number"]}</a>' for d in n["days"])
        days = ""
        for d in n["days"]:
            num = d["day_number"]
            days += f"""
<article class="day" id="day-{num}">
  <p class="day-num">{e(s['day_of'].format(n=num))}</p>
  <h2>{e(d['title'])}</h2>
  <p class="step"><a href="#opening">{e(s['opening_prayer'])}</a> — {e(s['opening_prayer_note'])}</p>
  <div class="reading">{paras(d['body_text'])}</div>
  <h3>{e(s['closing_prayer'])}</h3>
  <div class="prayer">{paras(d['closing_prayer'])}</div>
  <p class="to-top"><a href="#days">{e(s['back_to_top'])} ↑</a></p>
</article>"""
        others = [o for o in c["novenas"] if o["is_free"] and o["id"] != n["id"]]
        body = f"""
<article class="wrap novena">
  <header>
    <h1>{e(n['title'])}</h1>
    {disclosure}
    {meta_block(lang, n, c)}
    <p class="lead">{e(s['how_to'])}</p>
  </header>
  <details class="source-line"><summary>{e(s['source_label'])}</summary><p>{e(n['source'])}</p></details>
  <nav class="days-nav" id="days" aria-label="{e(s['days_nav'])}"><span>{e(s['days_nav'])}:</span>{days_nav}</nav>
  <section class="opening" id="opening">
    <h2>{e(s['opening_prayer'])}</h2>
    <p class="muted">{e(s['opening_prayer_note'])}</p>
    <div class="prayer">{paras(n['opening_prayer'])}</div>
  </section>
  {days}
  {store_block(lang, depth, 'novena_page', sl, s['in_app_heading'], s['in_app_body'])}
  {source_block(lang, n)}
  {about}
  <h2>{e(s['other_free'])}</h2>
  <ul class="cards">{''.join(novena_card(lang, o, c, depth) for o in others)}</ul>
</article>
"""
        title = s["novena_page_title"].format(title=n["title"])
        desc = s["novena_page_description"].format(title=n["title"])
        og = "assets/img/og-default.png"
    else:
        body = f"""
<article class="wrap novena summary">
  <header>
    <h1>{e(n['title'])}</h1>
    {disclosure}
    {meta_block(lang, n, c)}
  </header>
  <p class="lead">{e(s['summary_note'])}</p>
  {source_block(lang, n)}
  <p class="muted">{e(s['summary_sources'])}</p>
  {about}
  {store_block(lang, depth, 'novena_summary', sl)}
</article>
"""
        title = f"{n['title']} — Novena"
        desc = s["summary_page_description"].format(title=n["title"])
        og = "assets/img/og-default.png"
    # hreflang only between languages that carry the same novena id.
    alternates = {}
    for l in LANGS:
        if l == lang or any(x["id"] == n["id"] for x in load(l)["novenas"]):
            alternates[l] = f"{LANG_PREFIX[l]}novenas/{sl}/"
    return page(lang=lang, path=path, title=title, description=desc, body=body,
                depth=depth, og_image=og, alternates=alternates)


def build_support(lang: str) -> str:
    s = STRINGS[lang]
    depth = 1 if not LANG_PREFIX[lang] else 2
    privacy = rel(depth) + "privacy.html"
    faq = "".join(f"<details><summary>{e(q)}</summary><p>{a.format(privacy=privacy)}</p></details>"
                  for q, a in s["support_faq"])
    body = f"""
<section class="wrap prose">
  <h1>{e(s['support_title'])}</h1>
  <h2>{e(s['support_contact_h'])}</h2>
  <p>{s['support_contact']}</p>
  <div class="faq">{faq}</div>
  {f"<p>{e(s['support_rate'])}</p>" if PLAY_LIVE else ""}
</section>
"""
    return page(lang=lang, path=LANG_PREFIX[lang] + "support/", title=f"{s['support_title']} — Novena",
                description=s["support_description"], body=body, depth=depth,
                alternates={l: LANG_PREFIX[l] + "support/" for l in LANGS})


def build_press(lang: str) -> str:
    s = STRINGS[lang]
    depth = 1 if not LANG_PREFIX[lang] else 2
    r = rel(depth)
    facts = "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in s["press_facts"])
    shots = "".join(
        f'<li><a href="{r}assets/press/screenshot-{i}.png" download>'
        f'<img src="{r}assets/img/screen-{i}.png" alt="{e(s["shot_alts"][i - 1])}" width="540" height="960" loading="lazy">'
        f'{e(s["press_shot"])}</a></li>' for i in (2,))
    do = "".join(f"<li>{x}</li>" for x in s["press_do"])
    dont = "".join(f"<li>{x}</li>" for x in s["press_dont"])
    body = f"""
<section class="wrap prose">
  <h1>{e(s['press_title'])}</h1>
  <p class="lead">{e(s['press_intro'])}</p>
  <h2>{e(s['press_one_sentence_h'])}</h2>
  <p>{e(s['press_one_sentence'])}</p>
  <h2>{e(s['press_paragraph_h'])}</h2>
  <p>{e(s['press_paragraph'])}</p>
  <h2>{e(s['press_facts_h'])}</h2>
  <dl class="meta">{facts}</dl>
</section>
<section class="wrap">
  <h2>{e(s['press_assets_h'])}</h2>
  <ul class="press-assets">
    <li><a href="{r}assets/press/novena-icon-512.png" download><img src="{r}assets/img/icon-192.png" alt="Novena app icon" width="96" height="96">{e(s['press_icon'])}</a></li>
    <li><a href="{r}assets/press/novena-feature-graphic.png" download><img src="{r}assets/press/novena-feature-graphic.png" alt="Novena feature graphic" width="512" height="250" loading="lazy">{e(s['press_feature'])}</a></li>
  </ul>
  <ul class="press-assets shots-list">{shots}</ul>
</section>
<section class="wrap prose">
  <h2>{e(s['press_brand_h'])}</h2>
  <h3>{e(s['press_do_h'])}</h3><ul>{do}</ul>
  <h3>{e(s['press_dont_h'])}</h3><ul>{dont}</ul>
</section>
"""
    return page(lang=lang, path=LANG_PREFIX[lang] + "press/", title=f"{s['press_title']} — Novena",
                description=s["press_description"], body=body, depth=depth,
                alternates={l: LANG_PREFIX[l] + "press/" for l in LANGS})


def build_guide(lang: str, c: dict) -> str:
    s = STRINGS[lang]
    depth = 1 if not LANG_PREFIX[lang] else 2
    secs = "".join(f"<h2>{e(h)}</h2>" + "".join(f"<p>{p}</p>" for p in ps) for h, ps in s["guide_sections"])
    free = [n for n in c["novenas"] if n["is_free"]]
    body = f"""
<article class="wrap prose">
  <h1>{e(s['guide_title'])}</h1>
  {secs}
</article>
<section class="wrap">
  <h2>{e(s['guide_free_h'])}</h2>
  <p>{e(s['guide_free_intro'])}</p>
  <ul class="cards">{''.join(novena_card(lang, n, c, depth) for n in free)}</ul>
  {store_block(lang, depth, 'guide', 'what_is_a_novena', s['cta_heading'], s['cta_body'])}
  <p class="muted">{s['guide_source']}</p>
</section>
"""
    return page(lang=lang, path=LANG_PREFIX[lang] + "what-is-a-novena/", title=s["guide_title"],
                description=s["guide_description"], body=body, depth=depth,
                alternates={l: LANG_PREFIX[l] + "what-is-a-novena/" for l in LANGS})


PARISH_URL = "https://getnovena.app/parish/"


def qr_svg(url: str) -> str:
    """An inline SVG QR code, generated here at build time. No service is called."""
    import qrcode
    qr = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1"/>'
                    for y, row in enumerate(m) for x, v in enumerate(row) if v)
    return (f'<svg class="qr" viewBox="0 0 {n} {n}" role="img" aria-label="QR code for {e(url)}" '
            f'shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="#fff"/>'
            f'<g fill="#000">{rects}</g></svg>')


def build_parish(lang: str, c: dict) -> str:
    s = STRINGS[lang]
    depth = 1 if not LANG_PREFIX[lang] else 2
    r = rel(depth)
    body = f"""
<section class="wrap prose">
  <h1>Novena</h1>
  <p class="lead">{e(s['parish_intro'])}</p>
  <p>{e(s['parish_body'])}</p>
  <p><a class="button" href="{r}{LANG_PREFIX[lang]}novenas/st-jude/#day-1">{e(s['parish_start'])}</a></p>
  <p><a href="{r}{LANG_PREFIX[lang]}novenas/">{e(s['parish_all'])} →</a></p>
  {store_block(lang, depth, 'parish', 'qr_card')}
</section>
"""
    return page(lang=lang, path=LANG_PREFIX[lang] + "parish/", title=s["parish_title"],
                description=s["parish_description"], body=body, depth=depth, noindex=True)


def build_kit(lang: str) -> str:
    s = STRINGS[lang]
    depth = 1 if not LANG_PREFIX[lang] else 2
    qr = qr_svg(PARISH_URL)
    live = BASE_URL.startswith("https://getnovena.app/")
    warn = "" if live else f'<p class="disclosure no-print-hide">{e(s["kit_not_live"])}</p>'
    note = "".join(f"<p>{e(x)}</p>" for x in s["kit_note"])
    cards = "".join(f'<div class="qr-card"><p class="card-line">{e(s["kit_card_line"])}</p>{qr}'
                    f'<p class="card-sub">{e(s["kit_card_sub"])}<br>getnovena.app</p></div>' for _ in range(8))
    body = f"""
<section class="wrap prose screen-only">
  <h1>{e(s['kit_title'])}</h1>
  <p class="lead">{e(s['kit_intro'])}</p>
  {warn}
  <h2>{e(s['kit_bulletin_h'])}</h2>
  <p class="bulletin">{e(s['kit_bulletin'])}</p>
  <h2>{e(s['kit_note_h'])}</h2>
  <div class="note">{note}</div>
</section>
<div class="print-sheet poster">
  <p class="poster-mark">Novena</p>
  <p class="poster-line">{s['kit_poster_line']}</p>
  {qr}
  <p class="poster-sub">{e(s['kit_poster_sub'])}<br><strong>getnovena.app</strong></p>
  <p class="poster-foot">{e(s['kit_footer'])}</p>
</div>
<div class="print-sheet cards-sheet">{cards}</div>
"""
    return page(lang=lang, path=LANG_PREFIX[lang] + "parish-kit/", title=f"{s['kit_title']} — Novena",
                description=s["kit_description"], body=body, depth=depth, noindex=True)


def build_404() -> str:
    # Served for any unknown path at any depth, so every link is absolute
    # from the site root. On github.io the root is /novena-site/.
    s = STRINGS["en"]
    root = "/" + BASE_URL.split("://", 1)[1].split("/", 1)[1]
    body = f"""
<section class="wrap prose">
  <h1>{e(s['notfound_title'])}</h1>
  <p>{e(s['notfound_body'])}</p>
  <p><a href="{root}">{e(s['notfound_home'])}</a> · <a href="{root}novenas/">{e(s['notfound_novenas'])}</a></p>
</section>
"""
    out = page(lang="en", path="404.html", title=f"{s['notfound_title']} — Novena",
               description=s["notfound_body"], body=body, depth=0, noindex=True)
    # page() writes ./-relative asset links; make them root-absolute here.
    return out.replace('href="./', f'href="{root}').replace('src="./', f'src="{root}')


# ---------------------------------------------------------------------------
# Plumbing
# ---------------------------------------------------------------------------

def write(rel_path: str, text: str) -> None:
    out = ROOT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, "utf-8")


def main() -> None:
    if not (APP / "src/data/novenas.json").exists():
        sys.exit(f"Cannot find the app repository at {APP}. Set NOVENA_REPO.")
    urls: list[str] = []
    for lang in LANGS:
        c = load(lang)
        pre = LANG_PREFIX[lang]
        # Clear this language's generated novena pages so a novena that stops
        # being free cannot leave its full text behind.
        shutil.rmtree(ROOT / pre / "novenas", ignore_errors=True)
        write(pre + "index.html", build_home(lang, c)); urls.append(pre)
        write(pre + "novenas/index.html", build_index(lang, c)); urls.append(pre + "novenas/")
        for n in c["novenas"]:
            p = f"{pre}novenas/{slug(n['id'])}/"
            write(p + "index.html", build_novena(lang, n, c)); urls.append(p)
        write(pre + "what-is-a-novena/index.html", build_guide(lang, c)); urls.append(pre + "what-is-a-novena/")
        write(pre + "support/index.html", build_support(lang)); urls.append(pre + "support/")
        # Parish pages are noindex: the landing is for QR visitors, the kit is for printing.
        write(pre + "parish/index.html", build_parish(lang, c))
        write(pre + "parish-kit/index.html", build_kit(lang))
        write(pre + "press/index.html", build_press(lang)); urls.append(pre + "press/")
    urls.append("privacy.html")
    write("404.html", build_404())
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap.append(f"  <url><loc>{BASE_URL}{u}</loc><lastmod>{BUILD_DATE}</lastmod></url>")
    sitemap.append("</urlset>")
    write("sitemap.xml", "\n".join(sitemap) + "\n")
    write("robots.txt", f"User-agent: *\nAllow: /\nDisallow: /tools/\n\nSitemap: {BASE_URL}sitemap.xml\n")
    print(f"Built {len(urls)} URLs for {', '.join(LANGS)} at {BASE_URL} (PLAY_LIVE={PLAY_LIVE}).")


if __name__ == "__main__":
    main()
