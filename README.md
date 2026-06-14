# yesimthisgoofy

live at → **https://yesimthisgoofy.surge.sh**

🦀 powered by Rust (compiled to WebAssembly via wasm-pack)

a little something for someone. one button:

- **find me a taco bell 🌮** — gets your browser location, asks Rust→WASM, returns the 3 closest Taco Bells from a pre-baked North American dataset (~1,900 locations). Zero network calls during search. Results in <50ms.

## architecture

```
index.html ──module import──▶ pkg/tacobell_finder.js
                                          │
                                          ▼
                              pkg/tacobell_finder_bg.wasm
                              (Rust compiled to WASM)
                              ─ haversine + sort
                              ─ static NA_TACO_BELLS[1906] baked in
```

- `index.html` — UI, geolocation, render code (vanilla JS)
- `rust-tacobell/` — Rust crate, compiled to WASM. Pre-bakes the Taco Bell data via `build.rs`.
- `pkg/` — deployable WASM + JS glue (output of `wasm-pack build`)

## updating

### Code-only changes (UI tweaks, copy, styling)

Edit `index.html`, then:

```bash
cd ~/Coding/gf-site
surge . yesimthisgoofy.surge.sh
```

Live in ~5 seconds.

### Refreshing the Taco Bell dataset (~yearly)

OSM data drifts a little — locations open/close. Refresh by:

```bash
cd ~/Coding/gf-site/rust-tacobell
./refresh-data.sh                          # re-runs the Overpass query
wasm-pack build --target web --release     # rebuilds the WASM with new data
cp -r pkg ../pkg                           # copies the new artifacts to the site root
cd .. && surge . yesimthisgoofy.surge.sh
```

## hosting

Surge.sh Student tier (free, custom subdomain on `*.surge.sh`, HTTPS, 10-city CDN, Sectigo wildcard cert).

---

made with too much creativity & one of those crunchwraps.
