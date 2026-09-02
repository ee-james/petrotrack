# small html fetch-and-rewrite service so the electron browser panels can show
# any page without CORS getting in the way.
#
# GET /fetch?url=<target>&dark=true&no_images=false
#   - fetches the page server-side
#   - drops in a <base href> so relative css/js still loads
#   - optionally slaps a dark stylesheet on top
#   - optionally rips out images/figures
#   - rewrites <a> and <form> so clicking through stays inside the proxy
#     (and keeps the dark / no_images flags)

import re
from urllib.parse import urljoin, urlparse, urlencode, quote

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

app = FastAPI(title="web-proxy", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---- Dark-mode CSS ----
# goes in as the last stylesheet so it wins. !important only where pages
# fight inheritance.

DARK_CSS = """
/* reset to a dark base */
html { color-scheme: dark; }

html, body {
  background-color: #181818 !important;
  color: #d8d8d8 !important;
}

/* Generic containers */
div, section, article, main, aside, nav, header, footer,
p, li, td, th, caption, blockquote, pre, code, span {
  background-color: inherit;
  color: inherit;
  border-color: #3a3a3a !important;
}

/* Links */
a             { color: #6ab0f5 !important; }
a:visited     { color: #9a80d4 !important; }
a:hover       { color: #90c8ff !important; }

/* Inputs */
input, textarea, select, button {
  background: #252525 !important;
  color: #d8d8d8 !important;
  border-color: #484848 !important;
}

/* Tables */
table, thead, tbody, tfoot { background: #1e1e1e !important; }
th { background: #272727 !important; }
tr:nth-child(even) td { background: #222 !important; }

/* Code / pre */
code, pre, kbd, samp {
  background: #252525 !important;
  color: #ce9178 !important;
}

/* Blockquote */
blockquote { border-left-color: #555 !important; background: #1e1e1e !important; }

/* HR */
hr { border-color: #3a3a3a !important; }

/* wikipedia */
.mw-body, .mw-body-content       { background: #181818 !important; color: #d8d8d8 !important; }
.mw-page-container                { background: #181818 !important; }
.mw-header, #mw-head, #mw-panel  { background: #202020 !important; border-color: #3a3a3a !important; }
.vector-menu-content              { background: #202020 !important; }
.infobox, .wikitable              { background: #1e1e1e !important; border-color: #3a3a3a !important; }
.infobox th, .wikitable th        { background: #272727 !important; }
.catlinks                         { background: #1e1e1e !important; border-color: #3a3a3a !important; }
.toc                              { background: #1e1e1e !important; border-color: #3a3a3a !important; }
.reflist                          { color: #b8b8b8 !important; }
#p-search input                   { background: #252525 !important; color: #d8d8d8 !important; }

/* generic news / article sites */
.article-body, .story-body, .article__body { background: #181818 !important; color: #d8d8d8 !important; }
.headline, .article-headline, h1, h2, h3, h4, h5, h6 { color: #e8e8e8 !important; }
.byline, .author, .dateline { color: #999 !important; }
nav, .navbar, .site-header, .header { background: #202020 !important; border-color: #3a3a3a !important; }
.card, .widget, .sidebar { background: #1e1e1e !important; border-color: #3a3a3a !important; }
.tag, .label, .badge { background: #2a2a2a !important; color: #d8d8d8 !important; }
footer, .site-footer { background: #161616 !important; border-color: #3a3a3a !important; }
"""

# ---- Helpers ----

SKIP_SCHEMES = re.compile(r'^(#|mailto:|javascript:|tel:|data:)', re.I)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def proxy_url(request: Request, target: str, dark: bool, no_images: bool) -> str:
    # a /fetch url that points target back at us
    params = urlencode({"url": target, "dark": str(dark).lower(), "no_images": str(no_images).lower()})
    return f"/proxy/fetch?{params}"


# ---- Main endpoint ----

@app.get("/fetch", response_class=HTMLResponse)
async def fetch(
    request:   Request,
    url:       str  = Query(...,   description="Target URL to fetch"),
    dark:      bool = Query(True,  description="Inject dark-mode CSS"),
    no_images: bool = Query(False, description="Strip all images"),
):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return HTMLResponse("<html><body><p>Invalid URL - only http/https allowed.</p></body></html>", status_code=400)

    # basic ssrf guard - no loopback or private ranges
    hostname = parsed.hostname or ""
    if hostname in ("localhost", "127.0.0.1", "::1") or hostname.startswith("192.168.") or hostname.startswith("10."):
        return HTMLResponse("<html><body><p>Private network addresses are not allowed.</p></body></html>", status_code=403)

    base_origin = f"{parsed.scheme}://{parsed.netloc}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers=HEADERS)
    except httpx.RequestError as exc:
        return HTMLResponse(
            f"<html><body><p>Failed to fetch <code>{url}</code>: {exc}</p></body></html>",
            status_code=502,
        )

    content_type = resp.headers.get("content-type", "")
    if "html" not in content_type:
        # not html, hand it back untouched
        return Response(content=resp.content, media_type=content_type)

    soup = BeautifulSoup(resp.text, "lxml")

    # ---- Head injections ----
    head = soup.find("head")
    if not head:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)

    # <base> so relative asset urls resolve against the original domain
    for existing_base in soup.find_all("base"):
        existing_base.decompose()
    base_tag = soup.new_tag("base", href=base_origin + "/")
    head.insert(0, base_tag)

    if dark:
        style = soup.new_tag("style")
        style.string = DARK_CSS
        head.append(style)

    # ---- Strip images ----
    if no_images:
        for tag in soup.find_all(["img", "picture", "figure", "svg", "canvas"]):
            tag.decompose()
        # kill css background images too
        bg_style = soup.new_tag("style")
        bg_style.string = "* { background-image: none !important; }"
        head.append(bg_style)

    # ---- Keep <a> clicks inside the proxy ----
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if SKIP_SCHEMES.match(href):
            continue
        abs_url = urljoin(url, href)
        abs_parsed = urlparse(abs_url)
        if abs_parsed.scheme not in ("http", "https"):
            continue
        a["href"]   = proxy_url(request, abs_url, dark, no_images)
        a["target"] = "_self"

    # ---- Same for <form action> ----
    for form in soup.find_all("form", action=True):
        action = form["action"].strip()
        if SKIP_SCHEMES.match(action):
            continue
        abs_action = urljoin(url, action)
        abs_parsed  = urlparse(abs_action)
        if abs_parsed.scheme not in ("http", "https"):
            continue
        form["action"] = proxy_url(request, abs_action, dark, no_images)

    return HTMLResponse(str(soup), status_code=resp.status_code)


# ---- Health check ----

@app.get("/health")
async def health():
    return {"status": "ok"}
