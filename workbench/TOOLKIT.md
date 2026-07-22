# Qalam Badi — tooling & toolkit strategy

Living document. What we use, what we *should* use, where the gaps are, and a
proposed full toolkit. Grounded in the repo and the installed environment plus
three tool surveys (Eli Heuer's tooling; the headless CLI font ecosystem;
UFO-native font IDEs + `.fea` tooling), as of 2026-07. §6 is a brief for a
possible follow-up: designing a new Linux font tool.

---

## 0. The language question (framing)

Three ecosystems, and we straddle them on purpose:

| lang | role in fonts | our stance |
|------|---------------|-----------|
| **Python** | the mature, universal ecosystem — fontTools, ufoLib2, fontmake, defcon, ufo2ft, HarfBuzz bindings, fontbakery. Everything interoperates through it. | **Keep the pipeline here.** Non-negotiable for interop; the UFO/fontTools world *is* Python. Our `workbench/` is Python because it must read UFOs. |
| **Rust** | Google's forward bet — `fontc` (next-gen compiler), `fea-rs` (.fea), `skrifa`/`read-fonts`/`write-fonts`, `kurbo`, `norad`. Fast, single-binary, future-facing. Eli Heuer's `img2bez`/`bezy` are here too. | **Watch, don't rewrite.** Adopt specific mature binaries (e.g. a `.fea` compiler/linter) as CLI tools; don't port our stack. |
| **Go** | fewer font libraries, but excellent for CLI tools, glue, single-binary deploy — and our preference. | **Our custom tools live here.** We already ship a Go feature-generator (`scripts/arabic-features/`). New bespoke CLI utilities → Go. |

Guiding rule: **pipeline & glyph-introspection in Python (ecosystem gravity); our
own generators/CLI tools in Go (our comfort + deploy); pull in Rust binaries only
where they're clearly best and stable.**

---

## 1. What we use today (grounded)

### Build pipeline
- **fontmake** 3.12 — UFO/designspace → TTF/OTF (the spine).
- **fontTools** 4.63 — invoked ~26× across Makefile/scripts (ttx, subset, varLib, etc.).
- **ufo2ft**, **glyphsLib**, **defcon**, **ufoLib2** 0.18, **compreffor**, **ttfautohint-py** — transitive/pipeline members.
- **gftools** — invoked ~20× (Google Fonts packaging/fixing helpers).

### Our own generators (already programmatic)
- **`scripts/arabic-features/` (Go)** — writes each UFO's `features.fea` (Arabic
  shaping); has a `--check` mode. *This is why we don't need FontForge for features.*
- **Python injectors** — `make-stars.py`, `mark-anchors.py` etc. edit `features.fea`
  and anchors idempotently.
- **`scripts/` pipeline** (~Python) — the transform chain (narrow, soften, curve,
  proportional, kern, mark-anchors, masters …).

### QA / proof
- **fontbakery** (googlefonts profile) — invoked ~15×.
- **ufolint**, **diffenator2**.

### Rendering (what we actually invoke)
- **uharfbuzz** — Arabic shaping for word renders.
- **rsvg-convert** (system) — SVG → PNG for all our diagnostics.
- Hand-rolled SVG in `workbench/render.py` + the old `out/show/` scratch scripts.

### Our workbench (new, this session)
- **`workbench/anatomy.py`** — glyph-anatomy measurement (landmarks + metrics).
- **`workbench/render.py`** — annotated glyph → SVG/PNG.
- **`workbench/sheets.py`**, **`GLOSSARY.md`**.

---

## 2. Already installed but under-using (the big finding)

The CLI survey's headline: **we already own almost the entire Google stack,
including a full measurement toolkit** — we hand-rolled in `anatomy.py` things
that shipped libraries already do. All of these are in the venv now.

### Measurement — we reinvented some of this
| tool | ver | what it gives us | note vs our workbench |
|------|----:|------------------|-----------------------|
| **fontTools pens** | 4.63 | `statisticsPen` → area, center-of-mass, **slant/slope**, variance; `boundsPen`/`controlBoundsPen` → extrema; `flattenPen` → outline sampling; `momentsPen`, `areaPen` | our least-squares slope ≈ `statisticsPen` slant; our silhouette sampling ≈ `flattenPen` |
| **beziers.py** | 0.6 | `BezierPath`: extremes, tangents, **curvature**, arc length, self-intersection, offset, point-at-t | our corner/straight detection could ride on real curvature instead of perp-deviation |
| **kurbopy** | 0.13 | Rust `kurbo` bindings: arclen, curvature, nearest-point, offset, area — fast | **Rust under the hood** — fits the language axis without a rewrite |
| **freetype-py** | 2.3 | rasterize a glyph to a bitmap | the **on-ramp to medial-axis** (§4) |

### Rendering — we're hand-rolling SVG when these exist
| tool | ver | why |
|------|----:|-----|
| **blackrenderer** | 0.8 | headless font renderer (Cairo/Skia), COLR-aware → PNG/SVG/PDF |
| **drawbot-skia** | 0.5 | headless DrawBot API on Skia — scriptable proofs |
| **skia-python** | 144 | full Skia: render **and** path ops |
| **resvg-cli** | 0.44 | Rust SVG→PNG — **already installed; we call system `rsvg-convert` instead.** Standardize on `resvg`. |
| **uharfbuzz / vharfbuzz** | — | Arabic shaping in-process |

### QA / construction — installed, unused
| tool | ver | why |
|------|----:|-----|
| **collidoscope** | 0.6 | glyph **collision detection** (HarfBuzz + Shapely) — directly relevant to our mark-collision work |
| **shaperglot** | 1.2 | checks **Arabic shaping coverage** per language |
| **fontMath** | 0.10 | glyph arithmetic/interpolation — the **P-construction** (blend variants) |
| **skia-pathops / booleanOperations** | — | boolean outline ops for clean construction under the one-rule |
| **fontTools `varLib.interpolatable`** | 4.63 | master-compatibility QA (Bold/contrast) |
| **ufomerge** | 1.9 | programmatic glyph merge between UFOs |

**Immediate actions:** (a) re-base `workbench/anatomy.py` on `statisticsPen` +
`beziers`/`kurbopy` instead of hand-rolled math; (b) re-back `render.py` on
`blackrenderer`/`drawbot-skia` + `resvg`; (c) use `fontMath` for the unified form;
(d) wire `collidoscope`/`shaperglot` into QA.

---

## 3. Net-new worth installing (small, ranked)

| tool | install | for | notes |
|------|---------|-----|-------|
| **glyphtools** | `pip install glyphtools` | measurement | Simon Cozens; `get_glyph_metrics()` → width, LSB/RSB, **rise, run, stroke slope**; hands glyphs as `beziers.BezierPath`. Built on beziers (we have it). Last release 2022 but small/stable — pin it. |
| **HarfBuzz CLI utils** | `pacman -S harfbuzz-utils` | shaping/proof | `hb-shape` (glyph IDs+positions for an Arabic string — indispensable joining/mark debug), `hb-view`. Best-maintained project in the space. |
| **scikit-image + scipy** | `pip install scikit-image` | the medial-axis route (§4) | `skimage.morphology.medial_axis(return_distance=True)` → skeleton **+ per-point stroke half-width**. The only viable centreline path. |
| **foundrytools-cli** (`ftcli`) | `pip install foundrytools-cli` | inspect/fix | ergonomic CLI over fontTools; **fixes** what fontbakery reports. Install in an **isolated venv** — it fights our fontmake pins. |

Situational: `opentype-feature-freezer` (bake in a stylistic set), `afdko` (CFF
inspection), FontForge as an **external** system tool for autotrace only (never a
pip dep — its `import fontforge` setup breaks CI, already noted in `requirements.in`).

---

## 4. Gaps (build-our-own)

- **Stroke skeleton / medial-axis — the real gap.** We measure via *silhouette
  walks* (outline walls), not the true stroke centreline, so "return lay-down
  angle" measures a wall, not the pen path. **Confirmed unsolved by any
  off-the-shelf font tool** (both surveys). Nearest prior art is academic with no
  release: *StrokeStyles*, Berio et al., ACM TOG 2022. Concrete build path (~200
  lines, mostly libs we own):
  1. rasterize a glyph at high em with **freetype-py** / **skia-python**;
  2. **`skimage.medial_axis(img, return_distance=True)`** → skeleton + per-point
     half-width (the anatomy signal we're missing);
  3. fit polylines/béziers back with **beziers** / **kurbopy**;
  4. take corners/slopes from **beziers** curvature/tangents on the outline.
  Raster topology + vector precision — the current state of the art you can run
  headless.
- **Cohesive live preview** — edit glyph/`.fea` → rebuild → shape sample → see it.
  No turnkey "font live-server" exists; **Fontra is closest** (live in-browser
  reshape via a WASM shaper font). The CI/specimen version is ~30 lines of glue:
  `watchdog` on `sources/**` → Go feature-gen + fontmake/fontc → `vharfbuzz`/
  `hb-view` render → `preview.svg`.
- **`.fea` diagnostics in-editor** — **no true LSP for `.fea` exists anywhere.**
  VS Code has TextMate-grammar extensions only (`vscode-afdko` is the common one:
  highlighting + snippets, no semantics). `feaLib` (canonical, matches our build)
  has terse errors; **`fea-rs`** (Rust, googlefonts — same engine behind Fontra's
  shaper) has much better error-recovering diagnostics with precise locations.
  The only place you get *interactive* compiler-grade `.fea` feedback today is
  **inside Fontra**. → a real `.fea` LSP is an open opportunity (see §6).
- **A UFO-native "font IDE"** — none cohesive for Linux+Python+external-features.
  **Fontra** (github.com/fontra/fontra, active, Linux-first, Python server + web
  client, reads/writes UFO in place with auto-reload) is the standout — but a
  *component*, not a pipeline replacement, and its feature editor **can overwrite
  `features.fea`**, so it must be used view/preview-only against our generated
  features. **Bezy** (Eli Heuer, Rust, RTL/Arabic-first) is the promising upstart
  but pre-1.0 and crypto-entangled. See §6 for the landscape and the build option.

---

## 5. Full toolkit proposal

| layer | stack | status |
|-------|-------|--------|
| **Pipeline** | fontmake + fontTools + ufo2ft (Python) | keep |
| **Measurement** | `statisticsPen` + beziers + kurbopy + glyphtools; our `workbench/` as the domain layer on top; **+ new medial-axis module** | re-base + build |
| **Rendering** | blackrenderer / drawbot-skia + resvg (retire hand-rolled SVG+rsvg) | migrate |
| **Features** | Go generator (source of truth) + **feaLib** build-match + **fea-rs** for diagnostics + `vscode-afdko` syntax | assemble |
| **QA** | fontbakery + diffenator2 + **collidoscope** + **shaperglot** + interpolatable | add three |
| **Editor / IDE** | VS Code (`.fea`/Python cockpit) + **Fontra** (visual UFO edit + live shaping preview, *view/preview mode*) + watch/preview loop | assemble |
| **Custom CLI tools** | Go | policy |

**Language split confirmed by the surveys:** the measurement/rendering libs we'd
adopt are Python (ecosystem gravity — keep the pipeline there); `kurbopy`/`resvg`/
`fea-rs` give us Rust speed *as libraries/binaries* without a rewrite; our bespoke
generators stay Go.

---

## 6. The font-editor landscape & a new Linux tool (brief for a follow-up agent)

The editor landscape is genuinely thin — worth stating plainly for anyone picking
up "build a decent Linux font tool."

### What exists
| tool | verdict |
|------|---------|
| **Glyphs** (Mac, proprietary `.glyphs`) | the mindshare leader; Mac-only, own format — the thing to *replace*, not adopt |
| **FontForge** | the long-standing free option; not UFO-native, weak at the programming side (the stated pain), aging UI |
| **Fontra** (web, Python+JS, UFO/designspace-native) | **best existing free option.** Linux-first, in-place UFO, auto-reload, variable-first, live WASM `.fea` shaper. But: a *component* not a full IDE, plugin system still maturing, and its feature editor can clobber generated `features.fea` |
| **Bezy** (Rust, `norad` UFO) | RTL/**Arabic-first from day one**, very active, "AI-agent-assisted" pitch — but pre-1.0 and crypto-entangled (coin/treasury/micropayments); watch, don't depend |
| **TruFont / Runebender / Spoonbender** | dead or superseded |
| **RoboFont** (Mac, commercial) | the Python-scripting model to envy; no Linux |

### The gap a new tool would fill
A **Linux-native, UFO-native, programmable** environment that unifies what's now
scattered: glyph editing + externally-generated features (without clobbering) +
**real `.fea` diagnostics (an actual LSP — nobody has one)** + live HarfBuzz
preview + **built-in anatomy/skeleton measurement** (also nobody has it). The last
two are the differentiators; everything else Fontra mostly already does.

### Build on, don't reinvent
UFO I/O (`ufoLib2` Py / `norad` Rust), shaping (**HarfBuzz**), feature compile +
diagnostics (**fea-rs**), rendering (**skia** / blackrenderer), geometry
(`kurbo`/`beziers`), and — for the anatomy differentiator — the medial-axis module
from §4.

### Language choice for the tool (the real fork)
- **Go** (your preference): near-**greenfield** for font editing — no mature Go UFO/OT
  library beyond read-only `x/image/font/sfnt`. A Go tool would either **orchestrate**
  existing Python/Rust CLIs (realistic, plays to Go's single-binary/CLI strengths —
  and we already have a Go feature-gen to build on) or reimplement UFO/OT in Go (a
  large lift). Novelty is high; ecosystem support is low.
- **Rust**: **Bezy/`fontc`/`fea-rs`/`norad`/`kurbo`** already exist — contributing there
  gets furthest fastest, and Bezy is already Arabic-first. Google's direction.
- **Python**: contributing Fontra plugins (Python backend) reuses the most, but it's
  "improve the existing" rather than "a new tool."

**Suggested scoping for the follow-up agent:** decide among (a) a **Go orchestrator/TUI**
over the existing best-in-class CLIs + our workbench (lowest lift, most "ours",
Go-native); (b) **Fontra plugins** for the anatomy/measurement differentiator
(reuse the most); (c) **contribute to Bezy** (Rust, Arabic-first, but immature/crypto).
Option (a) matches the language policy and the differentiators (anatomy + preview)
that nobody else ships.
