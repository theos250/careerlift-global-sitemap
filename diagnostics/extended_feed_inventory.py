#!/usr/bin/env python3
"""Read-only extended inventory checks for CareerLift Global Blogger feeds."""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

ATOM = "http://www.w3.org/2005/Atom"
OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"
NS = {"atom": ATOM, "os": OPENSEARCH}
BASE = "https://www.careerliftglobal.com"
ALLOWED_HOSTS = {"www.careerliftglobal.com", "careerliftglobal.com", "www.blogger.com", "blogger.com"}


def build_url(path: str, **params: str) -> str:
    return f"{BASE}{path}?{urlencode({'alt': 'atom', **params})}"


def safe_fetch(url: str) -> ET.Element:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RuntimeError(f"Refusing unexpected request host: {parsed.hostname}")
    req = Request(url, headers={
        "User-Agent": "CareerLiftGlobal-FeedInventory/1.0 (+https://www.careerliftglobal.com/)",
        "Accept": "application/atom+xml, application/xml, text/xml",
    })
    with urlopen(req, timeout=35) as response:
        final = urlparse(response.geturl())
        print(f"    HTTP {response.status}; final host={final.hostname}")
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise RuntimeError(f"Unexpected redirect host: {final.hostname}")
        payload = response.read()
    root = ET.fromstring(payload)
    if root.tag != f"{{{ATOM}}}feed":
        raise RuntimeError(f"Expected Atom feed; got {root.tag!r}")
    return root


def describe(label: str, url: str) -> tuple[int, str | None]:
    print(f"\n[{label}]")
    print(f"  request={url}")
    try:
        root = safe_fetch(url)
    except (HTTPError, URLError, TimeoutError, ET.ParseError, RuntimeError) as exc:
        print(f"    ERROR: {type(exc).__name__}: {exc}")
        return 0, None
    entries = root.findall("atom:entry", NS)
    total = root.findtext("os:totalResults", default="not supplied", namespaces=NS)
    start = root.findtext("os:startIndex", default="not supplied", namespaces=NS)
    per_page = root.findtext("os:itemsPerPage", default="not supplied", namespaces=NS)
    updated = root.findtext("atom:updated", default="not supplied", namespaces=NS)
    dates = [e.findtext("atom:published", default="", namespaces=NS) for e in entries]
    dates = [d for d in dates if d]
    ids = [e.findtext("atom:id", default="", namespaces=NS) for e in entries]
    links = []
    for entry in entries:
        href = next((x.attrib.get("href") for x in entry.findall("atom:link", NS)
                     if x.attrib.get("rel", "alternate") == "alternate"), None)
        if href:
            links.append(href)
    nxt = next((x.attrib.get("href") for x in root.findall("atom:link", NS)
                if x.attrib.get("rel") == "next"), None)
    print(f"    entries={len(entries)}; alternate_links={len(links)}")
    print(f"    OpenSearch totalResults={total}; startIndex={start}; itemsPerPage={per_page}")
    print(f"    feed_updated={updated}")
    print(f"    published_range={min(dates) if dates else 'n/a'} .. {max(dates) if dates else 'n/a'}")
    print(f"    first_id={ids[0] if ids else 'n/a'}")
    print(f"    last_id={ids[-1] if ids else 'n/a'}")
    print(f"    rel_next={'YES' if nxt else 'NO'}")
    if nxt:
        p = urlparse(nxt)
        print(f"    next_host={p.hostname}; next_query={dict(parse_qsl(p.query))}")
        if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
            raise RuntimeError(f"Unexpected next-link host: {p.hostname}")
    return len(entries), nxt


def paged_inventory(label: str, first_url: str, max_pages: int = 30) -> None:
    print(f"\n=== PAGED INVENTORY: {label} ===")
    current = first_url
    seen: set[str] = set()
    unique_ids: set[str] = set()
    total_entries = 0
    for page in range(1, max_pages + 1):
        if current in seen:
            print("  STOP: repeated pagination URL")
            break
        seen.add(current)
        try:
            root = safe_fetch(current)
        except (HTTPError, URLError, TimeoutError, ET.ParseError, RuntimeError) as exc:
            print(f"  PAGE {page} ERROR: {type(exc).__name__}: {exc}")
            break
        entries = root.findall("atom:entry", NS)
        ids = [e.findtext("atom:id", default="", namespaces=NS) for e in entries]
        unique_ids.update(x for x in ids if x)
        total_entries += len(entries)
        dates = [e.findtext("atom:published", default="", namespaces=NS) for e in entries]
        dates = [d for d in dates if d]
        nxt = next((x.attrib.get("href") for x in root.findall("atom:link", NS)
                    if x.attrib.get("rel") == "next"), None)
        print(f"  page={page}; entries={len(entries)}; unique_ids_so_far={len(unique_ids)}; "
              f"published={min(dates) if dates else 'n/a'}..{max(dates) if dates else 'n/a'}; "
              f"next={'YES' if nxt else 'NO'}")
        if not nxt:
            break
        p = urlparse(nxt)
        if p.scheme != "https" or p.hostname not in ALLOWED_HOSTS:
            raise RuntimeError(f"Unexpected next-link host: {p.hostname}")
        current = nxt
        time.sleep(0.2)
    print(f"  RESULT: pages={len(seen)}; entries_seen={total_entries}; unique_entry_ids={len(unique_ids)}")


def main() -> int:
    print("CareerLift Global extended Blogger feed inventory (READ ONLY)")
    print("No files are written, no repository content is changed, and no sitemap is deployed.")

    # Metadata-only probe. Blogger may omit OpenSearch metadata; absence is not a zero count.
    describe("posts feed metadata probe max-results=0",
             build_url("/feeds/posts/default", **{"max-results": "0"}))

    # Test direct offsets beyond the previously observed 319-entry boundary.
    for start in ("320", "470", "620", "920", "1120"):
        describe(f"posts feed direct offset start-index={start}",
                 build_url("/feeds/posts/default", **{"max-results": "150", "start-index": start}))

    # Compare the default feed order with an explicitly published-date ordered feed.
    paged_inventory("posts orderby=published",
                    build_url("/feeds/posts/default", **{"max-results": "150", "orderby": "published"}))

    # Check whether Blogger exposes static Pages through its separate Atom feed.
    paged_inventory("static pages feed",
                    build_url("/feeds/pages/default", **{"max-results": "150"}), max_pages=10)

    print("\nDIAGNOSTIC COMPLETE. Interpret missing OpenSearch metadata cautiously; "
          "only observed feed responses are evidence. No deployment occurred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
