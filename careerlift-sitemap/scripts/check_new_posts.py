#!/usr/bin/env python3
"""Check whether Blogger's latest Atom feed contains URLs missing from the live sitemap."""
from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

ATOM = "http://www.w3.org/2005/Atom"
SITEMAP = "http://www.sitemaps.org/schemas/sitemap/0.9"
USER_AGENT = "CareerLiftGlobal-SitemapBot/1.0 (+https://www.careerliftglobal.com/)"

from generate_sitemap import canonicalize


def parse_feed_urls(payload: bytes, canonical_host: str) -> set[str]:
    root = ET.fromstring(payload)
    if root.tag != f"{{{ATOM}}}feed":
        raise ValueError("Latest Blogger response is not an Atom feed")
    urls: set[str] = set()
    for entry in root.findall(f"{{{ATOM}}}entry"):
        for link in entry.findall(f"{{{ATOM}}}link"):
            if link.attrib.get("rel", "alternate") == "alternate":
                loc = canonicalize(link.attrib.get("href", ""), canonical_host)
                if loc:
                    urls.add(loc)
                break
    if not urls:
        raise ValueError("Latest Blogger feed contained no canonical CareerLift post URLs")
    return urls


def parse_sitemap_urls(payload: bytes) -> set[str]:
    root = ET.fromstring(payload)
    if root.tag != f"{{{SITEMAP}}}urlset":
        raise ValueError("Live document is not a valid sitemap urlset")
    urls = {
        (node.text or "").strip()
        for node in root.findall(f"{{{SITEMAP}}}url/{{{SITEMAP}}}loc")
        if (node.text or "").strip()
    }
    if not urls:
        raise ValueError("Live sitemap contains no URLs")
    return urls


def has_new_posts(feed_xml: bytes, sitemap_xml: bytes, canonical_host: str) -> set[str]:
    return parse_feed_urls(feed_xml, canonical_host) - parse_sitemap_urls(sitemap_xml)


def fetch(url: str) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only HTTPS source URLs are accepted")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/xml, text/xml"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status} while checking {url}")
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", required=True)
    parser.add_argument("--sitemap", required=True)
    parser.add_argument("--site", default="https://www.careerliftglobal.com")
    args = parser.parse_args()
    site = urlparse(args.site)
    if site.scheme != "https" or not site.hostname or site.path not in {"", "/"}:
        raise SystemExit("--site must be an HTTPS origin")
    try:
        new_urls = has_new_posts(fetch(args.feed), fetch(args.sitemap), site.hostname.lower())
        if new_urls:
            print(f"NEW_POSTS={len(new_urls)}")
            for url in sorted(new_urls):
                print(f"NEW_URL={url}")
            print("changed=true")
        else:
            print("No new post URLs; live sitemap is current.")
            print("changed=false")
        return 0
    except (HTTPError, URLError, TimeoutError, ET.ParseError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
