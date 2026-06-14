# yesimthisgoofy

live at → **https://yesimthisgoofy.surge.sh**

🦀 powered by Rust (compiled to WebAssembly via wasm-pack)

a little something for someone. one button:

- **find me a taco bell 🌮** — gets your GPS location, asks Rust→WASM, returns the 3 closest Taco Bells from a pre-baked dataset. **All 3 results are tappable** and open Google Maps with a driving route from where you are to that store. Zero network calls during search. Results in <50 ms.

## architecture

```
index.html ──module import──▶ pkg/tacobell_finder.js
                                          │
                                          ▼
                              pkg/tacobell_finder_bg.wasm
                              (Rust compiled to WASM)
                              ─ haversine + sort
                              ─ static NA_TACO_BELLS[~1,980] baked in
```

- `index.html` — UI, geolocation, render code (vanilla JS). Map links always go to Google Maps with explicit `origin=<your GPS coords>` so the route starts from where you actually are.
- `rust-tacobell/` — Rust crate, compiled to WASM. Pre-bakes the Taco Bell data at compile time via `build.rs`.
- `pkg/` — deployable WASM + JS glue (output of `wasm-pack build`)

## the dataset (two sources, merged at build time)

The baked array combines two sources:

| Source | Coverage | Used for |
|---|---|---|
| `data/canadian-stores.json` | ~181 Canadian Taco Bells, scraped from [`tacobell.ca`](https://locations.tacobell.ca/) | **Authoritative for Canada** — Taco Bell's own store locator is the source of truth |
| `data/na-taco-bells.json` | ~1,900 US + Mexico Taco Bells via OpenStreetMap Overpass query | Coverage for everywhere outside Canada |

`build.rs` loads the Canadian-official set first, then merges OSM entries — skipping any OSM node within 250 m of a Canadian-official store (those are duplicates captured by both sources). End result: ~1,980 unique stores in the baked binary.

The reason: OSM has ghost stores in Canada (locations that closed but weren't removed from OSM). Taco Bell's own site doesn't.

## updating

### Code-only changes (UI / copy / styling)

Edit `index.html`. Bump the `?v=N` cache-bust query strings on the WASM imports (lines 12, 13, and the import inside `<script type="module">`) so phones don't serve stale assets. Then:

```bash
cd ~/Coding/gf-site
surge . yesimthisgoofy.surge.sh
```

Live in ~5 seconds.

### Refreshing the Canadian store list (~yearly)

```bash
cd ~/Coding/gf-site/rust-tacobell
python3 scrape-canada.py   # re-scrapes tacobell.ca → data/canadian-stores.json
```

### Refreshing the OSM dataset (~yearly)

```bash
cd ~/Coding/gf-site/rust-tacobell
./refresh-data.sh          # re-runs the Overpass bbox query → data/na-taco-bells.json
```

### Rebuilding the WASM after a data refresh

From the site root:

```bash
./build-wasm.sh            # wraps wasm-pack build + copies pkg/
surge . yesimthisgoofy.surge.sh
```

`build-wasm.sh --refresh` will run the Overpass refresh first (skips the Canadian scrape — run that manually when needed).

## toolchain

| Tool | Why | Install |
|---|---|---|
| `rustc` ≥ 1.91 | Compiles the crate | `rustup update stable` |
| `wasm-pack` | Bundles `.wasm` + JS glue | `cargo install wasm-pack --locked` |
| `wasm32-unknown-unknown` target | WASM compile target | `rustup target add wasm32-unknown-unknown` |
| `binaryen` (optional) | `wasm-opt` further shrinks the bundle (~30 KB). The crate sets `wasm-opt = false` in Cargo.toml; remove that override if you install binaryen | `sudo apt install binaryen` |
| `surge` | Deploys to surge.sh | `sudo npm install -g surge` |

## hosting

Surge.sh Student tier (free, custom subdomain on `*.surge.sh`, HTTPS, 10-city CDN, Sectigo wildcard cert). The `.surgeignore` file at the site root keeps `rust-tacobell/`, `.git/`, and markdown files out of the deploy — only `index.html` + `pkg/` ship.

---

made with too much creativity & one of those crunchwraps.
