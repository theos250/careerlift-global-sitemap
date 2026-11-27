#!/usr/bin/env python3
"""Build a consolidated XML sitemap from CareerLift Global's public Blogger Atom feed.

Read-only with respect to Blogger. Fails closed on unexpected feed hosts, malformed
XML, pagination loops, or a suspiciously small post inventory.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ATOM = "http://www.w3.org/2005/Atom"
SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"
NS = {"atom": ATOM}
ET.register_namespace("", SITEMAP)

SITE_URL = "https://www.careerliftglobal.com"
FEED_URL = SITE_URL + "/feeds/posts/default?alt=atom&max-results=150"
USER_AGENT = "CareerLiftGlobal-SitemapBot/1.0 (+https://www.careerliftglobal.com/)"


def canonicalize(url: str, canonical_host: str) -> str | None:
    """Accept only CareerLift's own HTTP(S) URLs; normalize to its canonical host."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    allowed = {canonical_host.lower(), canonical_host.lower().removeprefix("www.")}
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.hostname.lower() not in allowed:
        return None
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse(("https", canonical_host.lower(), path, "", "", ""))


def parse_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return None


def fetch_xml(url: str, allowed_feed_hosts: set[str]) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in allowed_feed_hosts:
        raise RuntimeError(f"Refusing unexpected feed/pagination host: {url}")
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/xml, text/xml",
    })
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Feed returned HTTP {response.status}: {url}")
        return response.read()


def discover_posts(feed_url: str, canonical_host: str, max_pages: int = 100) -> dict[str, str | None]:
    initial_host = urlparse(feed_url).hostname
    if not initial_host:
        raise RuntimeError("Blogger feed URL has no hostname")
    # Blogger may rewrite paginated Atom links to its canonical feed host.
    allowed_feed_hosts = {initial_host.lower(), "www.blogger.com", "blogger.com"}
    posts: dict[str, str | None] = {}
    visited: set[str] = set()
    current: str | None = feed_url
    page_count = 0

    while current:
        if current in visited:
            raise RuntimeError(f"Atom pagination loop detected: {current}")
        visited.add(current)
        page_count += 1
        if page_count > max_pages:
            raise RuntimeError(f"Feed exceeded safety limit of {max_pages} pages")

        try:
            root = ET.fromstring(fetch_xml(current, allowed_feed_hosts))
        except ET.ParseError as exc:
            raise RuntimeError(f"Invalid Atom XML at {current}: {exc}") from exc

        if root.tag != f"{{{ATOM}}}feed":
            raise RuntimeError(f"Expected Atom feed, received {root.tag!r}")

        for entry in root.findall("atom:entry", NS):
            links = entry.findall("atom:link", NS)
            href = next(
                (link.attrib.get("href") for link in links
                 if link.attrib.get("rel", "alternate") == "alternate"),
                None,
            )
            loc = canonicalize(href or "", canonical_host)
            if not loc:
                continue
            updated = parse_timestamp(entry.findtext("atom:updated", namespaces=NS))
            if loc not in posts or (updated and (not posts[loc] or updated > posts[loc])):
                posts[loc] = updated

        current = next(
            (link.attrib["href"] for link in root.findall("atom:link", NS)
             if link.attrib.get("rel") == "next" and link.attrib.get("href")),
            None,
        )
        if current:
            parsed_next = urlparse(current)
            if parsed_next.scheme != "https" or not parsed_next.hostname or parsed_next.hostname.lower() not in allowed_feed_hosts:
                raise RuntimeError(f"Unexpected Atom next-link host: {current}")
        time.sleep(0.1)

    return posts


def read_static_urls(path: Path, canonical_host: str) -> list[str]:
    if not path.exists():
        return []
    urls: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        loc = canonicalize(value, canonical_host)
        if not loc:
            raise ValueError(f"Static URL is not on the configured site: {value}")
        urls.append(loc)
    return urls


def build_xml(posts: dict[str, str | None], static_urls: list[str]) -> bytes:
    merged = dict(posts)
    for loc in static_urls:
        merged.setdefault(loc, None)

    urlset = ET.Element(f"{{{SITEMAP}}}urlset")
    for loc in sorted(merged):
        item = ET.SubElement(urlset, f"{{{SITEMAP}}}url")
        ET.SubElement(item, f"{{{SITEMAP}}}loc").text = loc
        if merged[loc]:
            ET.SubElement(item, f"{{{SITEMAP}}}lastmod").text = merged[loc]
    return ET.tostring(urlset, encoding="utf-8", xml_declaration=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", default=os.getenv("SITE_URL", SITE_URL))
    parser.add_argument("--feed", default=os.getenv("BLOGGER_FEED_URL", FEED_URL))
    parser.add_argument("--static-urls", default="careerlift-sitemap/static-urls.txt")
    parser.add_argument("--output", default="public/sitemap.xml")
    parser.add_argument("--min-posts", type=int, default=int(os.getenv("MIN_EXPECTED_POSTS", "800")))
    args = parser.parse_args()

    site = urlparse(args.site)
    if site.scheme != "https" or not site.hostname:
        raise SystemExit("--site must be an HTTPS origin")
    host = site.hostname.lower()

    try:
        posts = discover_posts(args.feed, host)
        if len(posts) < args.min_posts:
            raise RuntimeError(
                f"Safety check failed: found {len(posts)} unique posts; "
                f"minimum is {args.min_posts}. Existing published output will not be replaced."
            )
        static_urls = read_static_urls(Path(args.static_urls), host)
        xml_bytes = build_xml(posts, static_urls)

        root = ET.fromstring(xml_bytes)
        if root.tag != f"{{{SITEMAP}}}urlset":
            raise RuntimeError("Generated document is not a sitemap urlset")
        count = len(root.findall(f"{{{SITEMAP}}}url"))
        if not count or count > 50_000:
            raise RuntimeError(f"Invalid sitemap URL count: {count}")

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_bytes(xml_bytes)
        temp.replace(output)

        print(f"PASS: {len(posts)} unique published post URLs")
        print(f"PASS: {len(static_urls)} configured static URLs")
        print(f"PASS: {count} unique URLs written to {output}")
        print("PASS: XML parses with the official sitemap namespace")
        return 0
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
