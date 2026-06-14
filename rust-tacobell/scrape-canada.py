#!/usr/bin/env python3
"""Scrape Taco Bell Canada's official store list.

Pulls every /en/<province>/<city>/<addr-slug> URL out of the sitemap,
fetches each store page, extracts the embedded JSON-LD (each page has a
schema.org `FastFoodRestaurant` block with lat/lon + address), and writes
`data/canadian-stores.json`.

The site uses standard schema.org markup so the parsing is trivial.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = pathlib.Path(__file__).parent
SITEMAP = "https://locations.tacobell.ca/sitemap1.xml"
OUT = HERE / "data" / "canadian-stores.json"

UA = "Mozilla/5.0 (X11; Linux x86_64) yesimthisgoofy/1.0 (gift site, hi)"


def fetch(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def store_urls() -> list[str]:
    """Return de-duplicated /en/ store URLs from the sitemap."""
    xml = fetch(SITEMAP)
    urls = re.findall(
        r"https://locations\.tacobell\.ca/en/[a-z]+/[a-z\-]+/[a-z0-9\-]+",
        xml,
    )
    return sorted(set(urls))


def parse_store(url: str) -> dict | None:
    """Pull lat/lon/address/hours out of a store page's JSON-LD."""
    try:
        html = fetch(url)
    except Exception as e:
        print(f"  [skip] {url}: {e}", file=sys.stderr)
        return None

    # Each page embeds one or more schema.org JSON-LD blobs. The first
    # FastFoodRestaurant block is the store itself.
    # The site wraps JSON-LD in a `@graph` array. Find every block, dig
    # into the graph, take the first FastFoodRestaurant entry.
    for blob in re.findall(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    ):
        try:
            data = json.loads(blob.strip())
        except json.JSONDecodeError:
            continue
        graph = data.get("@graph") if isinstance(data, dict) else None
        if not isinstance(graph, list):
            # some blocks aren't wrapped
            graph = [data] if isinstance(data, dict) else []
        store = next(
            (n for n in graph if isinstance(n, dict) and n.get("@type") == "FastFoodRestaurant"),
            None,
        )
        if store is None:
            continue

        geo = store.get("geo") or {}
        addr = store.get("address") or {}
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is None or lon is None:
            continue

        # Compose the display address as "<street>, <city>".
        street = addr.get("streetAddress") or ""
        city = addr.get("addressLocality") or ""
        if street and city:
            display = f"{street}, {city}"
        elif street:
            display = street
        elif city:
            display = city
        else:
            display = "Taco Bell"

        opening_hours = ""
        oh_raw = store.get("openingHours")
        if isinstance(oh_raw, list) and oh_raw:
            opening_hours = "; ".join(oh_raw)
        elif isinstance(oh_raw, str):
            opening_hours = oh_raw

        return {
            "lat": float(lat),
            "lon": float(lon),
            "name": store.get("name") or "Taco Bell",
            "addr": display,
            "opening_hours": opening_hours,
            "url": url,
        }
    print(f"  [no JSON-LD] {url}", file=sys.stderr)
    return None


def main() -> int:
    print(f"Fetching sitemap: {SITEMAP}")
    urls = store_urls()
    print(f"  {len(urls)} unique Canadian store URLs")

    print("Fetching individual store pages (parallel)…")
    stores: list[dict] = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = {ex.submit(parse_store, u): u for u in urls}
        for i, fut in enumerate(as_completed(futures), start=1):
            s = fut.result()
            if s is not None:
                stores.append(s)
            if i % 25 == 0:
                print(f"  {i}/{len(urls)} done, {len(stores)} stores extracted")

    stores.sort(key=lambda s: (s["addr"], s["lat"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stores, indent=2, ensure_ascii=False))
    print(f"\n✓ wrote {len(stores)} stores to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
