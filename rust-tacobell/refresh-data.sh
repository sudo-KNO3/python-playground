#!/usr/bin/env bash
# Refresh the baked Taco Bell dataset.
#
# Re-runs the Overpass query for North America (US + Canada + Mexico) and
# overwrites data/na-taco-bells.json. After this, run `wasm-pack build` to
# rebuild the .wasm with the new data.

set -e
cd "$(dirname "$0")"

echo "Fetching North American Taco Bell dataset from Overpass…"
mkdir -p data
curl -s --max-time 90 https://overpass-api.de/api/interpreter \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode 'data=[out:json][timeout:60];(node["amenity"="fast_food"]["name"~"^Taco Bell",i](14.0,-170.0,75.0,-50.0);node["amenity"="fast_food"]["brand"~"^Taco Bell",i](14.0,-170.0,75.0,-50.0););out tags center;' \
  > data/na-taco-bells.json

count=$(python3 -c "import json,sys; print(len([e for e in json.load(open('data/na-taco-bells.json'))['elements'] if 'lat' in e]))")
echo "  $count Taco Bell entries written to data/na-taco-bells.json"
echo "  next: wasm-pack build --target web --release"
