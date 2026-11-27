#!/usr/bin/env python3
"""Read-only sequential start-index scan for Blogger post feed."""
from __future__ import annotations
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

BASE = "https://www.careerliftglobal.com/feeds/posts/default"
ATOM = "http://www.w3.org/2005/Atom"
NS = {"a": ATOM}
ALLOWED = {"www.careerliftglobal.com", "careerliftglobal.com", "www.blogger.com", "blogger.com"}

def main() -> int:
    print("READ-ONLY direct offset scan. No files, commits, sitemap writes, or deployment.")
    all_ids: set[str] = set()
    total_entries = 0
    for start in range(1, 1501, 25):
        url = BASE + "?" + urlencode({"alt": "atom", "max-results": "25", "start-index": str(start)})
        req = Request(url, headers={"User-Agent": "CareerLiftGlobal-FeedOffsetScan/1.0", "Accept": "application/atom+xml"})
        try:
            with urlopen(req, timeout=30) as response:
                final = urlparse(response.geturl())
                if response.status != 200 or final.scheme != "https" or final.hostname not in ALLOWED:
                    print(f"STOP unexpected response at start-index={start}: {response.status} {response.geturl()}")
                    break
                root = ET.fromstring(response.read())
        except Exception as exc:
            print(f"ERROR at start-index={start}: {type(exc).__name__}: {exc}")
            break
        entries = root.findall("a:entry", NS)
        ids = {e.findtext("a:id", default="", namespaces=NS) for e in entries}
        ids.discard("")
        new = ids - all_ids
        all_ids.update(ids)
        dates = [e.findtext("a:published", default="", namespaces=NS) for e in entries]
        dates = [x for x in dates if x]
        total_entries += len(entries)
        print(f"start={start}; returned={len(entries)}; new_ids={len(new)}; unique_total={len(all_ids)}; "
              f"published={min(dates) if dates else 'n/a'}..{max(dates) if dates else 'n/a'}")
        if not entries:
            print("No entries at this offset; scan continues to test for later gaps.")
        time.sleep(0.12)
    print(f"SUMMARY: raw_entries={total_entries}; unique_post_ids={len(all_ids)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
