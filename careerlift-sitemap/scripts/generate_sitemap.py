#!/usr/bin/env python3
"""Build a consolidated XML sitemap from CareerLift Global's public Blogger Atom feed.

Uses Blogger's observed start-index behavior with overlapping offset windows.
The generator is read-only with respect to Blogger and fails closed when discovery
or the minimum inventory safety check cannot be completed.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ATOM = "http://www.w3.org/2005/Atom"
SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"
NS = {"atom": ATOM}
ET.register_namespace("", SITEMAP)

SITE_URL = "https://www.careerliftglobal.com"
FEED_URL = SITE_URL + "/feeds/posts/default?alt=atom&max-results=25"
USER_AGENT = "CareerLiftGlobal-SitemapBot/1.0 (+https://www.careerliftglobal.com/)"
PAGE_SIZE = 25
OFFSET_OVERLAP = 5
EMPTY_OFFSET_LIMIT = 20
MAX_START_INDEX = 5000
MAX_REQUESTS = 600
REQUEST_DELAY_SECONDS = 0.15


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


def build_offset_url(feed_url: str, start_index: int, page_size: int) -> str:
    parsed = urlparse(feed_url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params.update({"alt": "atom", "max-results": str(page_size), "start-index": str(start_index)})
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(params), ""))


def fetch_feed_page(feed_url: str, start_index: int, page_size: int) -> list[ET.Element]:
    parsed = urlparse(feed_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RuntimeError("Blogger feed URL must use HTTPS and include a hostname")
    allowed_hosts = {parsed.hostname.lower(), "www.blogger.com", "blogger.com"}
    request_url = build_offset_url(feed_url, start_index, page_size)
    request = Request(request_url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/xml, text/xml",
    })
    with urlopen(request, timeout=30) as response:
        final = urlparse(response.geturl())
        if response.status != 200:
            raise RuntimeError(f"Feed returned HTTP {response.status}: {request_url}")
        if final.scheme != "https" or not final.hostname or final.hostname.lower() not in allowed_hosts:
            raise RuntimeError(f"Refusing unexpected feed redirect host: {response.geturl()}")
        try:
            root = ET.fromstring(response.read())
        except ET.ParseError as exc:
            raise RuntimeError(f"Invalid Atom XML at {request_url}: {exc}") from exc
    if root.tag != f"{{{ATOM}}}feed":
        raise RuntimeError(f"Expected Atom feed, received {root.tag!r}")
    return root.findall("atom:entry", NS)


def discover_posts(
    feed_url: str,
    canonical_host: str,
    *,
    page_size: int = PAGE_SIZE,
    overlap: int = OFFSET_OVERLAP,
    empty_offset_limit: int = EMPTY_OFFSET_LIMIT,
    max_start_index: int = MAX_START_INDEX,
    max_requests: int = MAX_REQUESTS,
    request_delay: float = REQUEST_DELAY_SECONDS,
) -> dict[str, str | None]:
    """Discover published posts with overlapping direct start-index requests."""
    if page_size < 2 or overlap < 1 or overlap >= page_size:
        raise ValueError("Require page_size >= 2 and 1 <= overlap < page_size")
    posts: dict[str, str | None] = {}
    seen_entry_ids: set[str] = set()
    start_index = 1
    empty_streak = 0
    requests = 0

    while start_index <= max_start_index and requests < max_requests and empty_streak < empty_offset_limit:
        entries = fetch_feed_page(feed_url, start_index, page_size)
        requests += 1
        empty_streak = 0 if entries else empty_streak + 1

        for entry in entries:
            entry_id = (entry.findtext("atom:id", default="", namespaces=NS) or "").strip()
            if entry_id:
                seen_entry_ids.add(entry_id)

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

        # Retain overlap. When Blogger returns <= overlap entries, probe the
        # next offset individually instead of jumping over sparse feed ranges.
        step = max(1, len(entries) - overlap) if entries else 1
        start_index += step
        if request_delay:
            time.sleep(request_delay)

    if empty_streak < empty_offset_limit:
        raise RuntimeError(
            "Feed discovery did not reach the required consecutive-empty stopping condition "
            f"(requests={requests}, next_start_index={start_index}, empty_streak={empty_streak}). "
            "Refusing to treat a partial scan as complete."
        )
    if not posts:
        raise RuntimeError("Feed discovery returned no canonical CareerLift post URLs")
    print(
        f"Feed scan: {requests} requests; {len(seen_entry_ids)} unique Blogger entry IDs; "
        f"{len(posts)} canonical post URLs; stopped after {empty_streak} empty offsets."
    )
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
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate the complete sitemap without writing an output file.")
    args = parser.parse_args()

    site = urlparse(args.site)
    if site.scheme != "https" or not site.hostname or site.path not in {"", "/"}:
        raise SystemExit("--site must be an HTTPS origin")
    host = site.hostname.lower()

    try:
        posts = discover_posts(args.feed, host)
        if len(posts) < args.min_posts:
            raise RuntimeError(
                f"Safety check failed: found {len(posts)} unique posts; "
                f"minimum is {args.min_posts}. No output will be written."
            )
        static_urls = read_static_urls(Path(args.static_urls), host)
        xml_bytes = build_xml(posts, static_urls)
        root = ET.fromstring(xml_bytes)
        if root.tag != f"{{{SITEMAP}}}urlset":
            raise RuntimeError("Generated document is not a sitemap urlset")
        count = len(root.findall(f"{{{SITEMAP}}}url"))
        if not count or count > 50_000:
            raise RuntimeError(f"Invalid sitemap URL count: {count}")

        if args.dry_run:
            print(f"PASS: {len(posts)} unique published post URLs")
            print(f"PASS: {len(static_urls)} configured static URLs")
            print(f"PASS: {count} unique URLs validated; dry-run wrote no files")
            print("PASS: XML parses with the official sitemap namespace")
            return 0

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
