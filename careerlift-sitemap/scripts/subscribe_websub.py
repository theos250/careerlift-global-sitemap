#!/usr/bin/env python3
"""Discover Blogger's advertised WebSub hub and subscribe the Netlify callback."""
from __future__ import annotations

import os
import sys
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

ATOM = "http://www.w3.org/2005/Atom"
FEED = "https://www.careerliftglobal.com/feeds/posts/default?alt=atom"
CALLBACK = "https://effervescent-concha-70a086.netlify.app/.netlify/functions/blogger-websub"
USER_AGENT = "CareerLiftGlobal-WebSubSubscriber/1.0 (+https://www.careerliftglobal.com/)"


def discover() -> tuple[str, str]:
    request = Request(FEED, headers={"User-Agent": USER_AGENT, "Accept": "application/atom+xml, application/xml"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Blogger feed returned HTTP {response.status}")
        root = ET.fromstring(response.read())
    if root.tag != f"{{{ATOM}}}feed":
        raise RuntimeError("Blogger did not return an Atom feed")
    hubs = [
        link.attrib.get("href", "")
        for link in root.findall(f"{{{ATOM}}}link")
        if link.attrib.get("rel") == "hub"
    ]
    self_links = [
        link.attrib.get("href", "")
        for link in root.findall(f"{{{ATOM}}}link")
        if link.attrib.get("rel") == "self"
    ]
    if not hubs:
        raise RuntimeError("Blogger's Atom feed did not advertise a rel=hub endpoint; refusing to guess a hub")
    hub = hubs[0]
    parsed_hub = urlparse(hub)
    if parsed_hub.scheme != "https" or not parsed_hub.hostname:
        raise RuntimeError(f"Refusing non-HTTPS or invalid hub URL: {hub}")
    topic = self_links[0] if self_links else FEED
    parsed_topic = urlparse(topic)
    if parsed_topic.scheme != "https" or parsed_topic.hostname not in {"www.careerliftglobal.com", "careerliftglobal.com"}:
        raise RuntimeError(f"Refusing unexpected Blogger topic URL: {topic}")
    return hub, topic


def main() -> int:
    secret = os.environ.get("WEBSUB_SECRET", "")
    if len(secret) < 32:
        print("ERROR: WEBSUB_SECRET must contain at least 32 characters.", file=sys.stderr)
        return 1
    try:
        hub, topic = discover()
        payload = urlencode({
            "hub.callback": CALLBACK,
            "hub.mode": "subscribe",
            "hub.topic": topic,
            "hub.secret": secret,
            "hub.lease_seconds": "604800",
        }).encode()
        request = Request(
            hub,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"WebSub hub returned HTTP {response.status}")
            print(f"Subscription request accepted by {hub} (HTTP {response.status}).")
            print(f"Topic: {topic}")
            print(f"Callback: {CALLBACK}")
            print("The hub must complete the callback verification challenge before notifications are active.")
        return 0
    except (HTTPError, URLError, TimeoutError, ET.ParseError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
