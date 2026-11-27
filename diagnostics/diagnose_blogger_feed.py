#!/usr/bin/env python3
"""Read-only diagnostics for CareerLift Global's public Blogger Atom feed."""
from __future__ import annotations

import argparse
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ATOM = "http://www.w3.org/2005/Atom"
OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"
NS = {"atom": ATOM, "os": OPENSEARCH}
DEFAULT_FEED = "https://www.careerliftglobal.com/feeds/posts/default?alt=atom&max-results=150"
ALLOWED_HOSTS = {"www.careerliftglobal.com", "careerliftglobal.com", "www.blogger.com", "blogger.com"}


def fetch(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() not in ALLOWED_HOSTS:
        raise RuntimeError(f"Refusing unexpected feed host: {url}")
    request = Request(url, headers={
        "User-Agent": "CareerLiftGlobal-FeedDiagnostics/1.0 (+https://www.careerliftglobal.com/)",
        "Accept": "application/atom+xml, application/xml, text/xml",
    })
    with urlopen(request, timeout=30) as response:
        print(f"  HTTP status: {response.status}")
        print(f"  Response URL host: {urlparse(response.geturl()).hostname}")
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", default=DEFAULT_FEED)
    parser.add_argument("--max-pages", type=int, default=100)
    args = parser.parse_args()

    current = args.feed
    visited: set[str] = set()
    unique_posts: set[str] = set()
    page = 0

    print("CareerLift Global Blogger Atom feed diagnostic (read-only)")
    print(f"Initial feed host: {urlparse(args.feed).hostname}")
    print(f"Maximum pages: {args.max_pages}")

    while current:
        if current in visited:
            raise RuntimeError(f"Pagination loop detected at page {page + 1}")
        if page >= args.max_pages:
            raise RuntimeError(f"Exceeded maximum page limit ({args.max_pages})")
        visited.add(current)
        page += 1
        print(f"\nPAGE {page}")
        print(f"  Request URL host: {urlparse(current).hostname}")
        root = ET.fromstring(fetch(current))
        if root.tag != f"{{{ATOM}}}feed":
            raise RuntimeError(f"Expected Atom feed; received {root.tag!r}")

        entries = root.findall("atom:entry", NS)
        before = len(unique_posts)
        page_urls = []
        for entry in entries:
            href = next((link.attrib.get("href") for link in entry.findall("atom:link", NS)
                         if link.attrib.get("rel", "alternate") == "alternate"), None)
            if href:
                page_urls.append(href)
                unique_posts.add(href)

        total = root.findtext("os:totalResults", default="not supplied", namespaces=NS)
        start = root.findtext("os:startIndex", default="not supplied", namespaces=NS)
        per_page = root.findtext("os:itemsPerPage", default="not supplied", namespaces=NS)
        next_link = next((link.attrib.get("href") for link in root.findall("atom:link", NS)
                          if link.attrib.get("rel") == "next" and link.attrib.get("href")), None)

        print(f"  Atom entries: {len(entries)}")
        print(f"  Alternate links: {len(page_urls)}")
        print(f"  New unique entry links: {len(unique_posts) - before}")
        print(f"  OpenSearch totalResults: {total}")
        print(f"  OpenSearch startIndex: {start}")
        print(f"  OpenSearch itemsPerPage: {per_page}")
        print(f"  rel=next present: {'YES' if next_link else 'NO'}")
        if next_link:
            parsed_next = urlparse(next_link)
            print(f"  Next-link host: {parsed_next.hostname}")
            print(f"  Next-link query keys: {','.join(sorted({k for k, _ in __import__('urllib.parse', fromlist=['parse_qsl']).parse_qsl(parsed_next.query)})) or '(none)'}")
            if parsed_next.scheme != "https" or not parsed_next.hostname or parsed_next.hostname.lower() not in ALLOWED_HOSTS:
                raise RuntimeError(f"Unexpected pagination host: {parsed_next.hostname}")
        current = next_link
        if current:
            time.sleep(0.2)

    print("\nSUMMARY")
    print(f"  Pages fetched: {page}")
    print(f"  Unique raw entry links: {len(unique_posts)}")
    print("  No files were written and no sitemap was deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
